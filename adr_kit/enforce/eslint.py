"""ESLint configuration generation from ADRs.

Design decisions:
- Parse ADRs to extract library/framework decisions
- Generate ESLint rules to ban disallowed imports
- Support common patterns like "Use React Query instead of X"
- Generate rules for deprecated patterns based on superseded ADRs
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Any, Union, Optional

from ..core.parse import find_adr_files, parse_adr_file, ParseError
from ..core.model import ADRStatus


class ESLintRuleExtractor:
    """Extract ESLint rules from ADR content."""
    
    def __init__(self):
        # Common patterns for identifying banned imports/libraries
        self.ban_patterns = [
            # "Don't use X", "Avoid X", "Ban X"
            r"(?i)(?:don't\s+use|avoid|ban|deprecated?)\s+([a-zA-Z0-9\-_@/]+)",
            # "Use Y instead of X"
            r"(?i)use\s+([a-zA-Z0-9\-_@/]+)\s+instead\s+of\s+([a-zA-Z0-9\-_@/]+)",
            # "Replace X with Y"
            r"(?i)replace\s+([a-zA-Z0-9\-_@/]+)\s+with\s+([a-zA-Z0-9\-_@/]+)",
            # "No longer use X"
            r"(?i)no\s+longer\s+use\s+([a-zA-Z0-9\-_@/]+)",
        ]
        
        # Common library name mappings
        self.library_mappings = {
            "react-query": "@tanstack/react-query",
            "react query": "@tanstack/react-query",
            "axios": "axios",
            "fetch": "fetch",
            "lodash": "lodash",
            "moment": "moment",
            "date-fns": "date-fns",
            "dayjs": "dayjs",
            "jquery": "jquery",
            "underscore": "underscore",
        }
    
    def extract_from_adr(self, adr) -> Dict[str, Any]:
        """Extract ESLint rules from a single ADR.
        
        Args:
            adr: The ADR object to extract rules from
            
        Returns:
            Dictionary with extracted rule information
        """
        rules = {
            "banned_imports": [],
            "preferred_imports": {},
            "custom_rules": []
        }
        
        # Only extract rules from accepted ADRs
        if adr.front_matter.status != ADRStatus.ACCEPTED:
            return rules
        
        content = f"{adr.front_matter.title} {adr.content}".lower()
        
        # Extract banned imports using patterns
        for pattern in self.ban_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if isinstance(match, tuple):
                    # Pattern with replacement (e.g., "use Y instead of X")
                    if len(match) == 2:
                        preferred, banned = match
                        banned_lib = self._normalize_library_name(banned.strip())
                        preferred_lib = self._normalize_library_name(preferred.strip())
                        
                        if banned_lib:
                            rules["banned_imports"].append(banned_lib)
                            if preferred_lib:
                                rules["preferred_imports"][banned_lib] = preferred_lib
                else:
                    # Simple ban pattern
                    banned_lib = self._normalize_library_name(match.strip())
                    if banned_lib:
                        rules["banned_imports"].append(banned_lib)
        
        # Check for frontend-specific rules
        if "frontend" in (adr.front_matter.tags or []):
            rules.update(self._extract_frontend_rules(content))
        
        # Check for backend-specific rules
        if any(tag in (adr.front_matter.tags or []) for tag in ["backend", "api", "server"]):
            rules.update(self._extract_backend_rules(content))
        
        return rules
    
    def _normalize_library_name(self, name: str) -> Optional[str]:
        """Normalize library name to common import format."""
        name = name.lower().strip()
        
        # Check direct mappings
        if name in self.library_mappings:
            return self.library_mappings[name]
        
        # Skip common words that aren't libraries
        skip_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by"}
        if name in skip_words or len(name) < 2:
            return None
        
        # Basic validation - should look like a library name
        if re.match(r'^[a-zA-Z0-9\-_@/]+$', name):
            return name
        
        return None
    
    def _extract_frontend_rules(self, content: str) -> Dict[str, Any]:
        """Extract frontend-specific ESLint rules."""
        rules = {"custom_rules": []}
        
        # React-specific patterns
        if "react" in content:
            if "hooks" in content and ("don't" in content or "avoid" in content):
                rules["custom_rules"].append({
                    "rule": "react-hooks/rules-of-hooks",
                    "severity": "error"
                })
        
        return rules
    
    def _extract_backend_rules(self, content: str) -> Dict[str, Any]:
        """Extract backend-specific ESLint rules."""
        rules = {"custom_rules": []}
        
        # Node.js specific patterns
        if "node" in content or "nodejs" in content:
            if "synchronous" in content and ("don't" in content or "avoid" in content):
                rules["custom_rules"].append({
                    "rule": "no-sync",
                    "severity": "error"
                })
        
        return rules


def generate_eslint_config(adr_directory: Union[Path, str] = "docs/adr") -> str:
    """Generate ESLint configuration from ADRs.
    
    Args:
        adr_directory: Directory containing ADR files
        
    Returns:
        JSON string with ESLint configuration
    """
    extractor = ESLintRuleExtractor()
    
    # Find and parse all ADRs
    adr_files = find_adr_files(adr_directory)
    all_banned_imports = set()
    preferred_imports = {}
    custom_rules = []
    
    for file_path in adr_files:
        try:
            adr = parse_adr_file(file_path, strict=False)
            if not adr:
                continue
                
            rules = extractor.extract_from_adr(adr)
            
            # Collect banned imports
            all_banned_imports.update(rules["banned_imports"])
            
            # Collect preferred imports
            preferred_imports.update(rules["preferred_imports"])
            
            # Collect custom rules
            custom_rules.extend(rules["custom_rules"])
            
        except ParseError:
            continue
    
    # Build ESLint configuration
    eslint_config = {
        "rules": {},
        "overrides": []
    }
    
    # Add import restrictions if any banned imports found
    if all_banned_imports:
        banned_patterns = []
        for lib in all_banned_imports:
            banned_patterns.append({
                "name": lib,
                "message": f"Import of '{lib}' is not allowed according to ADR decisions"
            })
        
        eslint_config["rules"]["no-restricted-imports"] = [
            "error",
            {
                "paths": banned_patterns
            }
        ]
    
    # Add custom rules
    for rule in custom_rules:
        eslint_config["rules"][rule["rule"]] = rule["severity"]
    
    # Add comment explaining the configuration
    config_with_comments = {
        "_comment": "This ESLint configuration was generated from ADR decisions. Do not edit manually.",
        "_adr_source": str(adr_directory),
        "_generated_rules": {
            "banned_imports": list(all_banned_imports),
            "preferred_imports": preferred_imports
        },
        **eslint_config
    }
    
    return json.dumps(config_with_comments, indent=2)


def generate_eslint_overrides(adr_directory: Union[Path, str] = "docs/adr") -> Dict[str, Any]:
    """Generate ESLint override configuration for specific file patterns.
    
    Args:
        adr_directory: Directory containing ADR files
        
    Returns:
        Dictionary with override configuration
    """
    # This could be extended to create file-pattern-specific rules
    # based on ADR tags or content analysis
    
    overrides = []
    
    # Example: Stricter rules for production files
    overrides.append({
        "files": ["src/components/**/*.tsx", "src/pages/**/*.tsx"],
        "rules": {
            "no-console": "error",
            "no-debugger": "error"
        }
    })
    
    # Example: Relaxed rules for test files
    overrides.append({
        "files": ["**/*.test.{js,ts,jsx,tsx}", "**/*.spec.{js,ts,jsx,tsx}"],
        "rules": {
            "no-console": "warn"
        }
    })
    
    return {"overrides": overrides}