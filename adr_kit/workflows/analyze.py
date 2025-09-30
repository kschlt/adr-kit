"""Analyze Project Workflow - For existing projects wanting to adopt ADR-Kit."""

import os
from collections import Counter
from pathlib import Path
from typing import Any

from ..core.parse import find_adr_files
from .base import BaseWorkflow, WorkflowError, WorkflowResult, WorkflowStatus


class AnalyzeProjectWorkflow(BaseWorkflow):
    """Workflow for analyzing existing projects and generating agent prompts.

    This workflow is pure automation that:
    1. Scans project structure and detects technologies
    2. Checks for existing ADR setup
    3. Generates intelligent prompts for agents to analyze architectural decisions

    The agent provides ALL intelligence - this workflow just provides data and prompts.
    """

    def execute(self, **kwargs: Any) -> WorkflowResult:
        """Execute project analysis workflow.

        Args:
            **kwargs: Keyword arguments that should contain:
                project_path: Path to project root (defaults to current directory)
                focus_areas: Optional focus areas like ["dependencies", "patterns", "architecture"]

        Returns:
            WorkflowResult with detected technologies and analysis prompt for agent
        """
        # Extract parameters from kwargs
        project_path = kwargs.get("project_path")
        focus_areas = kwargs.get("focus_areas")

        self._start_workflow("Analyze Project")

        try:
            # Step 1: Validate inputs and setup
            project_root = self._execute_step(
                "validate_inputs", self._validate_inputs, project_path
            )

            # Step 1.5: Validate ADR directory (but allow creation if needed)
            self._execute_step(
                "validate_adr_directory", self._validate_adr_directory_for_analysis
            )

            # Step 2: Scan project structure
            project_structure = self._execute_step(
                "scan_project_structure", self._scan_project_structure, project_root
            )

            # Step 3: Detect technologies
            detected_technologies = self._execute_step(
                "detect_technologies",
                self._detect_technologies,
                project_root,
                project_structure,
            )

            # Step 4: Check existing ADR setup
            existing_adr_info = self._execute_step(
                "check_existing_adrs", self._check_existing_adrs, project_root
            )

            # Step 5: Generate analysis prompt for agent
            analysis_prompt = self._execute_step(
                "generate_analysis_prompt",
                self._generate_analysis_prompt,
                detected_technologies,
                existing_adr_info,
                focus_areas,
            )

            # Build project context summary
            project_context = {
                "technologies": detected_technologies["technologies"],
                "confidence_scores": detected_technologies["confidence_scores"],
                "project_structure": project_structure,
                "existing_adrs": {
                    "count": existing_adr_info["adr_count"],
                    "directory": (
                        str(existing_adr_info["adr_directory"])
                        if existing_adr_info["adr_directory"]
                        else None
                    ),
                    "files": existing_adr_info["adr_files"],
                },
                "suggested_focus": analysis_prompt["suggested_focus"],
            }

            # Set workflow output data
            self._set_workflow_data(
                detected_technologies=detected_technologies["technologies"],
                technology_confidence=detected_technologies["confidence_scores"],
                existing_adr_count=existing_adr_info["adr_count"],
                existing_adr_directory=(
                    str(existing_adr_info["adr_directory"])
                    if existing_adr_info["adr_directory"]
                    else None
                ),
                analysis_prompt=analysis_prompt["prompt"],
                suggested_focus=analysis_prompt["suggested_focus"],
                project_context=project_context,
            )

            # Add agent guidance
            if existing_adr_info["adr_count"] > 0:
                guidance = f"Found {existing_adr_info['adr_count']} existing ADRs. Use the analysis prompt to identify missing architectural decisions and create additional ADRs as needed."
                next_steps = [
                    "Follow the analysis prompt to review existing architectural decisions",
                    "Identify architectural decisions not yet documented",
                    "Use adr_create() for each new architectural decision you identify",
                    "Consider updating existing ADRs if they're incomplete",
                ]
            else:
                guidance = "No existing ADRs found. Use the analysis prompt to identify all architectural decisions and create initial ADR set."
                next_steps = [
                    "Follow the analysis prompt to analyze the entire project architecture",
                    "Identify all significant architectural decisions made in the project",
                    "Use adr_create() for each architectural decision you identify",
                    "Start with the most fundamental decisions (framework choices, data layer, etc.)",
                ]

            self._add_agent_guidance(guidance, next_steps)

            self._complete_workflow(
                success=True,
                message=f"Project analysis completed - found {len(detected_technologies['technologies'])} technologies",
                status=WorkflowStatus.SUCCESS,
            )

        except WorkflowError as e:
            self.result.add_error(str(e))
            self._complete_workflow(
                success=False,
                message="Project analysis failed",
                status=WorkflowStatus.FAILED,
            )
        except Exception as e:
            self.result.add_error(f"Unexpected error: {str(e)}")
            self._complete_workflow(
                success=False,
                message=f"Project analysis failed: {str(e)}",
                status=WorkflowStatus.FAILED,
            )

        return self.result

    def _validate_inputs(self, project_path: str | None) -> Path:
        """Validate inputs and return project root path."""
        if project_path:
            project_root = Path(project_path)
        else:
            project_root = Path.cwd()

        if not project_root.exists():
            raise WorkflowError(f"Project path does not exist: {project_root}")

        if not project_root.is_dir():
            raise WorkflowError(f"Project path is not a directory: {project_root}")

        return project_root

    def _validate_adr_directory_for_analysis(self) -> None:
        """Validate ADR directory for analysis workflow."""
        # For analysis, we need the parent directory to exist so we can potentially create ADR directory
        parent_dir = self.adr_dir.parent
        if not parent_dir.exists():
            raise WorkflowError(f"ADR parent directory does not exist: {parent_dir}")

        # If ADR directory exists, it must be a directory and writable
        if self.adr_dir.exists():
            if not self.adr_dir.is_dir():
                raise WorkflowError(f"ADR path is not a directory: {self.adr_dir}")

            # Check if we can write to the directory
            try:
                test_file = self.adr_dir / ".adr_kit_test"
                test_file.touch()
                test_file.unlink()
            except Exception as e:
                raise WorkflowError(
                    f"Cannot write to ADR directory: {self.adr_dir} - {e}"
                ) from e

    def _scan_project_structure(self, project_root: Path) -> dict[str, Any]:
        """Scan project structure to understand layout and files."""

        structure: dict[str, Any] = {
            "total_files": 0,
            "directories": [],
            "file_types": Counter(),
            "config_files": [],
            "package_managers": [],
            "common_directories": [],
        }

        # Define patterns to look for
        config_patterns = [
            "package.json",
            "package-lock.json",
            "yarn.lock",
            "requirements.txt",
            "setup.py",
            "pyproject.toml",
            "Pipfile",
            "Cargo.toml",
            "go.mod",
            "build.gradle",
            "pom.xml",
            ".eslintrc*",
            "tsconfig.json",
            "webpack.config.*",
            "Dockerfile",
            "docker-compose.yml",
            ".env*",
        ]

        common_dir_patterns = [
            "src",
            "lib",
            "app",
            "components",
            "services",
            "utils",
            "test",
            "tests",
            "spec",
            "__tests__",
            "docs",
            "documentation",
            "config",
            "configs",
            "settings",
        ]

        try:
            for root, dirs, files in os.walk(project_root):
                # Skip hidden directories and common ignore patterns
                dirs[:] = [
                    d
                    for d in dirs
                    if not d.startswith(".")
                    and d
                    not in ["node_modules", "__pycache__", "target", "build", "dist"]
                ]

                structure["directories"].extend([Path(root) / d for d in dirs])

                for file in files:
                    if not file.startswith("."):
                        structure["total_files"] += 1

                        # Track file extensions
                        suffix = Path(file).suffix.lower()
                        if suffix:
                            structure["file_types"][suffix] += 1

                        # Check for config files
                        for pattern in config_patterns:
                            if file.startswith(pattern.replace("*", "")):
                                structure["config_files"].append(str(Path(root) / file))

                # Check for common directories
                for dir_name in dirs:
                    if dir_name.lower() in common_dir_patterns:
                        structure["common_directories"].append(
                            str(Path(root) / dir_name)
                        )

        except Exception as e:
            raise WorkflowError(f"Failed to scan project structure: {e}") from e

        return structure

    def _detect_technologies(
        self, project_root: Path, structure: dict[str, Any]
    ) -> dict[str, Any]:
        """Detect technologies based on project structure and files."""

        technologies = []
        confidence_scores = {}

        # Technology detection patterns
        tech_patterns = {
            # Frontend frameworks
            "React": {
                "files": ["package.json"],
                "content_patterns": ['"react":', "import React", 'from "react"'],
                "extensions": [".jsx", ".tsx"],
            },
            "Vue": {
                "files": ["package.json"],
                "content_patterns": ['"vue":', "import Vue", ".vue"],
                "extensions": [".vue"],
            },
            "Angular": {
                "files": ["package.json", "angular.json"],
                "content_patterns": ['"@angular/', "import { Component }"],
                "extensions": [".ts"],
            },
            # Backend frameworks
            "Express.js": {
                "files": ["package.json"],
                "content_patterns": [
                    '"express":',
                    'require("express")',
                    "import express",
                ],
            },
            "FastAPI": {
                "files": ["requirements.txt", "pyproject.toml"],
                "content_patterns": ["fastapi", "from fastapi import"],
            },
            "Django": {
                "files": ["requirements.txt", "manage.py"],
                "content_patterns": ["django", "DJANGO_SETTINGS_MODULE"],
            },
            "Flask": {
                "files": ["requirements.txt"],
                "content_patterns": ["flask", "from flask import"],
            },
            # Languages
            "TypeScript": {
                "files": ["tsconfig.json", "package.json"],
                "content_patterns": ['"typescript":', '"@types/'],
                "extensions": [".ts", ".tsx"],
            },
            "Python": {
                "extensions": [".py"],
                "files": ["requirements.txt", "setup.py", "pyproject.toml"],
            },
            "JavaScript": {"extensions": [".js", ".jsx"], "files": ["package.json"]},
            "Rust": {"files": ["Cargo.toml"], "extensions": [".rs"]},
            "Go": {"files": ["go.mod", "go.sum"], "extensions": [".go"]},
            # Databases
            "PostgreSQL": {
                "content_patterns": ["postgresql", "psycopg2", "pg", "postgres"]
            },
            "MySQL": {"content_patterns": ["mysql", "pymysql", "mysql2"]},
            "MongoDB": {"content_patterns": ["mongodb", "mongoose", "pymongo"]},
            "Redis": {"content_patterns": ["redis", "ioredis"]},
            # Tools
            "Docker": {
                "files": ["Dockerfile", "docker-compose.yml", "docker-compose.yaml"]
            },
            "Webpack": {
                "files": ["webpack.config.js", "webpack.config.ts"],
                "content_patterns": ['"webpack":'],
            },
            "Vite": {
                "files": ["vite.config.js", "vite.config.ts"],
                "content_patterns": ['"vite":'],
            },
        }

        # Check each technology
        for tech_name, patterns in tech_patterns.items():
            confidence: float = 0.0

            # Check file extensions
            if "extensions" in patterns:
                for ext in patterns["extensions"]:
                    if (
                        ext in structure["file_types"]
                        and structure["file_types"][ext] > 0
                    ):
                        confidence += min(structure["file_types"][ext] * 0.1, 0.5)

            # Check specific files
            if "files" in patterns:
                for file_pattern in patterns["files"]:
                    for config_file in structure["config_files"]:
                        if file_pattern in config_file:
                            confidence += 0.3

                            # Check content patterns if available
                            if "content_patterns" in patterns:
                                try:
                                    content = Path(config_file).read_text(
                                        encoding="utf-8"
                                    )
                                    for pattern in patterns["content_patterns"]:
                                        if pattern in content:
                                            confidence += 0.2
                                except Exception:
                                    pass  # Skip file read errors

            # Check content patterns in all relevant files
            if "content_patterns" in patterns and confidence == 0:
                # Do a broader search if we haven't found anything yet
                try:
                    for config_file in structure["config_files"][:10]:  # Limit search
                        content = Path(config_file).read_text(encoding="utf-8")
                        for pattern in patterns["content_patterns"]:
                            if pattern in content:
                                confidence += 0.1
                                break
                except Exception:
                    pass

            # Add technology if confidence is high enough
            if confidence >= 0.3:
                technologies.append(tech_name)
                confidence_scores[tech_name] = min(confidence, 1.0)

        return {"technologies": technologies, "confidence_scores": confidence_scores}

    def _check_existing_adrs(self, project_root: Path) -> dict[str, Any]:
        """Check if project already has ADRs set up."""

        # Common ADR directory locations (relative to project root)
        possible_adr_dirs = [
            project_root / "docs" / "adr",
            project_root / "docs" / "adrs",
            project_root / "docs" / "decisions",
            project_root / "adr",
            project_root / "adrs",
            project_root / "decisions",
            project_root / "architecture" / "decisions",
        ]

        # Also check the configured ADR directory
        if self.adr_dir not in possible_adr_dirs:
            possible_adr_dirs.append(self.adr_dir)

        existing_adr_info: dict[str, Any] = {
            "adr_directory": None,
            "adr_count": 0,
            "adr_files": [],
        }

        for adr_dir in possible_adr_dirs:
            if adr_dir.exists() and adr_dir.is_dir():
                try:
                    adr_files = find_adr_files(adr_dir)
                    if adr_files:
                        existing_adr_info["adr_directory"] = str(adr_dir)
                        existing_adr_info["adr_count"] = len(adr_files)
                        existing_adr_info["adr_files"] = [str(f) for f in adr_files]
                        break
                except Exception:
                    continue  # Skip directories we can't read

        return existing_adr_info

    def _generate_analysis_prompt(
        self,
        detected_technologies: dict[str, Any],
        existing_adr_info: dict[str, Any],
        focus_areas: list[str] | None,
    ) -> dict[str, Any]:
        """Generate analysis prompt for the agent."""

        technologies = detected_technologies["technologies"]
        adr_count = existing_adr_info["adr_count"]

        # Build context-aware prompt
        prompt_parts = [
            "Please analyze this project for architectural decisions that should be documented as ADRs.",
            "",
            "**Project Context:**",
            f"- Detected technologies: {', '.join(technologies) if technologies else 'Unable to detect specific technologies'}",
            (
                f"- Existing ADRs: {adr_count} found"
                if adr_count > 0
                else "- No existing ADRs found"
            ),
            "",
        ]

        if adr_count > 0:
            prompt_parts.extend(
                [
                    "**Analysis Focus:**",
                    "1. Review existing ADRs to understand what's already documented",
                    "2. Identify architectural decisions that are missing from the ADR set",
                    "3. Look for inconsistencies between code and documented decisions",
                    "4. Propose new ADRs for undocumented architectural choices",
                    "",
                ]
            )
        else:
            prompt_parts.extend(
                [
                    "**Analysis Focus:**",
                    "1. Identify all significant architectural decisions made in this project",
                    "2. Focus on framework choices, data architecture, API design, and deployment patterns",
                    "3. Look for established conventions and patterns in the codebase",
                    "4. Propose ADRs for each major architectural decision you identify",
                    "",
                ]
            )

        # Add technology-specific guidance
        if technologies:
            prompt_parts.extend(["**Technology-Specific Areas to Examine:**"])

            for tech in technologies:
                if tech in ["React", "Vue", "Angular"]:
                    prompt_parts.append(
                        f"- {tech}: Component architecture, state management, routing decisions"
                    )
                elif tech in ["Express.js", "FastAPI", "Django", "Flask"]:
                    prompt_parts.append(
                        f"- {tech}: API design patterns, middleware choices, authentication strategy"
                    )
                elif tech in ["PostgreSQL", "MySQL", "MongoDB"]:
                    prompt_parts.append(
                        f"- {tech}: Database schema design, migration strategy, connection patterns"
                    )
                elif tech == "TypeScript":
                    prompt_parts.append(
                        f"- {tech}: Type system usage, configuration choices, strict mode settings"
                    )
                elif tech == "Docker":
                    prompt_parts.append(
                        f"- {tech}: Containerization strategy, multi-stage builds, orchestration"
                    )

            prompt_parts.append("")

        # Add focus area guidance if provided
        if focus_areas:
            prompt_parts.extend(
                [
                    "**Specific Focus Areas Requested:**",
                    *[f"- {area.title()}" for area in focus_areas],
                    "",
                ]
            )

        # Add action guidance
        prompt_parts.extend(
            [
                "**Instructions:**",
                "1. Examine the codebase thoroughly for architectural patterns and decisions",
                "2. For each significant architectural decision you identify:",
                "   - Consider the context that led to this decision",
                "   - Identify the alternatives that were likely considered",
                "   - Understand the consequences and trade-offs",
                "   - Draft an ADR using adr_create() with comprehensive rationale",
                "",
                "3. Focus on decisions that:",
                "   - Affect multiple parts of the system",
                "   - Have significant impact on development workflow",
                "   - Establish patterns other developers should follow",
                "   - Involve technology choices or architectural patterns",
                "",
                "4. Wait for human approval before accepting each proposed ADR",
                "",
                "Start your analysis now and propose ADRs for the architectural decisions you discover.",
            ]
        )

        prompt = "\n".join(prompt_parts)

        # Generate suggested focus areas based on detected technologies
        suggested_focus = []
        if any(tech in technologies for tech in ["React", "Vue", "Angular"]):
            suggested_focus.append("frontend_architecture")
        if any(
            tech in technologies
            for tech in ["Express.js", "FastAPI", "Django", "Flask"]
        ):
            suggested_focus.append("api_design")
        if any(
            tech in technologies for tech in ["PostgreSQL", "MySQL", "MongoDB", "Redis"]
        ):
            suggested_focus.append("data_architecture")
        if "Docker" in technologies:
            suggested_focus.append("deployment_strategy")
        if "TypeScript" in technologies:
            suggested_focus.append("type_system")

        return {"prompt": prompt, "suggested_focus": suggested_focus}
