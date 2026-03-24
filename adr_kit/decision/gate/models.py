"""Data models for the preflight policy gate system."""

from enum import Enum

from pydantic import BaseModel, Field


class GateDecision(str, Enum):
    """Possible outcomes from the preflight policy gate."""

    ALLOWED = "allowed"  # Choice is explicitly allowed, proceed
    REQUIRES_ADR = "requires_adr"  # Choice needs human approval via ADR
    BLOCKED = "blocked"  # Choice is explicitly denied
    CONFLICT = "conflict"  # Choice conflicts with existing ADRs


class CategoryRule(BaseModel):
    """Rule for categorizing technical choices."""

    category: str = Field(
        ..., description="Category name (e.g., 'runtime_dependency', 'framework')"
    )
    patterns: list[str] = Field(..., description="Regex patterns to match choice names")
    keywords: list[str] = Field(
        default_factory=list, description="Keywords that indicate this category"
    )
    examples: list[str] = Field(
        default_factory=list, description="Example choices in this category"
    )


class NameMapping(BaseModel):
    """Mapping for normalizing choice names and aliases."""

    canonical_name: str = Field(..., description="The canonical/preferred name")
    aliases: list[str] = Field(
        ..., description="Alternative names that map to the canonical name"
    )


class GateConfig(BaseModel):
    """Configuration for the preflight policy gate."""

    # Default policies
    default_dependency_policy: GateDecision = Field(
        GateDecision.REQUIRES_ADR,
        description="Default action for new runtime dependencies",
    )
    default_framework_policy: GateDecision = Field(
        GateDecision.REQUIRES_ADR,
        description="Default action for new frameworks/libraries",
    )
    default_tool_policy: GateDecision = Field(
        GateDecision.ALLOWED, description="Default action for development tools"
    )

    # Allow/deny lists
    always_allow: list[str] = Field(
        default_factory=list, description="Choices that are always allowed without ADR"
    )
    always_deny: list[str] = Field(
        default_factory=list, description="Choices that are always blocked"
    )
    development_tools: list[str] = Field(
        default_factory=lambda: [
            "eslint",
            "prettier",
            "jest",
            "vitest",
            "webpack",
            "vite",
            "typescript",
            "babel",
            "rollup",
            "esbuild",
            "parcel",
            "pytest",
            "black",
            "mypy",
            "ruff",
            "pre-commit",
            "husky",
            "lint-staged",
            "nodemon",
            "concurrently",
        ],
        description="Development tools that typically don't need ADRs",
    )

    # Categorization rules
    categories: list[CategoryRule] = Field(
        default_factory=lambda: [
            CategoryRule(
                category="runtime_dependency",
                patterns=[r"^[^@].*", r"^@[^/]+/[^/]+$"],  # Regular packages
                keywords=["runtime", "production", "dependency"],
                examples=["react", "express", "fastapi", "requests"],
            ),
            CategoryRule(
                category="framework",
                patterns=[r".*framework.*", r".*-cli$", r"create-.*"],
                keywords=["framework", "cli", "generator", "boilerplate"],
                examples=["next.js", "vue-cli", "create-react-app", "django"],
            ),
            CategoryRule(
                category="build_tool",
                patterns=[r".*webpack.*", r".*vite.*", r".*rollup.*"],
                keywords=["build", "bundler", "compiler"],
                examples=["webpack", "vite", "rollup", "esbuild"],
            ),
        ]
    )

    # Name mappings for normalization
    name_mappings: list[NameMapping] = Field(
        default_factory=lambda: [
            NameMapping(canonical_name="react", aliases=["reactjs", "react.js"]),
            NameMapping(canonical_name="vue", aliases=["vuejs", "vue.js"]),
            NameMapping(
                canonical_name="@tanstack/react-query",
                aliases=["react-query", "tanstack-query"],
            ),
            NameMapping(canonical_name="fastapi", aliases=["fast-api", "FastAPI"]),
            NameMapping(canonical_name="requests", aliases=["python-requests"]),
            NameMapping(canonical_name="axios", aliases=["axios-http"]),
        ]
    )

    # Metadata
    version: str = Field("1.0", description="Config version")
    created_by: str = Field("adr-kit", description="Who created this config")

    def normalize_name(self, choice_name: str) -> str:
        """Normalize a choice name using the name mappings."""
        choice_name = choice_name.lower().strip()

        for mapping in self.name_mappings:
            if choice_name == mapping.canonical_name.lower():
                return mapping.canonical_name
            if choice_name in [alias.lower() for alias in mapping.aliases]:
                return mapping.canonical_name

        return choice_name

    def categorize_choice(self, choice_name: str) -> str | None:
        """Determine the category of a technical choice."""
        import re

        normalized_name = self.normalize_name(choice_name)

        # Check if it's a development tool
        if normalized_name in [tool.lower() for tool in self.development_tools]:
            return "development_tool"

        # Check against category patterns
        for category in self.categories:
            # Check patterns
            for pattern in category.patterns:
                if re.match(pattern, normalized_name, re.IGNORECASE):
                    return category.category

            # Check keywords (in choice name)
            for keyword in category.keywords:
                if keyword.lower() in normalized_name.lower():
                    return category.category

        # Default categorization based on common patterns
        if any(
            dev_tool in normalized_name
            for dev_tool in ["test", "lint", "format", "build"]
        ):
            return "development_tool"

        # Default to runtime dependency if unclear
        return "runtime_dependency"

    def to_file(self, file_path: str) -> None:
        """Save configuration to a JSON file."""
        import json

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.model_dump(exclude_none=True), f, indent=2, sort_keys=True)

    @classmethod
    def from_file(cls, file_path: str) -> "GateConfig":
        """Load configuration from a JSON file."""
        import json
        from pathlib import Path

        path = Path(file_path)
        if not path.exists():
            # Return default config if file doesn't exist - mypy needs explicit defaults
            return cls(
                default_dependency_policy=GateDecision.REQUIRES_ADR,
                default_framework_policy=GateDecision.REQUIRES_ADR,
                default_tool_policy=GateDecision.ALLOWED,
                version="1.0",
                created_by="adr-kit",
            )

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        return cls.model_validate(data)
