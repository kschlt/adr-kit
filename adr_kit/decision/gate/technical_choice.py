"""Models for representing technical choices that need gate evaluation."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ChoiceType(str, Enum):
    """Types of technical choices that can be evaluated by the gate."""

    DEPENDENCY = "dependency"  # Adding a new runtime dependency
    FRAMEWORK = "framework"  # Adopting a new framework or major library
    TOOL = "tool"  # Development/build tool
    ARCHITECTURE = "architecture"  # Architectural pattern or approach
    LANGUAGE = "language"  # Programming language choice
    DATABASE = "database"  # Database technology
    CLOUD_SERVICE = "cloud_service"  # Cloud service or provider
    API_DESIGN = "api_design"  # API design approach
    OTHER = "other"  # Other technical choices


class TechnicalChoice(BaseModel):
    """Base class for representing a technical choice that needs evaluation."""

    choice_type: ChoiceType = Field(..., description="Type of technical choice")
    name: str = Field(
        ..., description="Name of the choice (e.g., 'react', 'postgresql')"
    )
    context: str = Field(..., description="Context or reason for the choice")
    alternatives_considered: list[str] = Field(
        default_factory=list, description="Other options that were considered"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata about the choice"
    )

    def get_canonical_name(self) -> str:
        """Get the canonical name for this choice."""
        # This will be overridden in subclasses for specific normalization
        return self.name.lower().strip()

    def get_search_terms(self) -> list[str]:
        """Get terms for searching existing ADRs."""
        terms = [self.name, self.get_canonical_name()]
        terms.extend(self.alternatives_considered)

        # Add context keywords
        import re

        context_words = re.findall(r"\b\w+\b", self.context.lower())
        terms.extend([word for word in context_words if len(word) > 3])

        return list(set(terms))  # Remove duplicates

    def to_search_description(self) -> str:
        """Create a description suitable for searching related ADRs."""
        return f"{self.choice_type.value} choice: {self.name} - {self.context}"


class DependencyChoice(TechnicalChoice):
    """A choice about adding a runtime dependency."""

    choice_type: ChoiceType = Field(
        default=ChoiceType.DEPENDENCY, description="Always dependency"
    )
    package_name: str = Field(..., description="Package/library name")
    version_constraint: str | None = Field(
        None, description="Version constraint (e.g., '^1.0.0')"
    )
    ecosystem: str = Field(..., description="Package ecosystem (npm, pypi, gem, etc.)")
    is_dev_dependency: bool = Field(
        False, description="Whether this is a development dependency"
    )
    replaces: list[str] | None = Field(None, description="Dependencies this replaces")

    def get_canonical_name(self) -> str:
        """Get canonical package name with ecosystem normalization."""
        # Handle scoped packages
        if self.package_name.startswith("@"):
            return self.package_name.lower()

        # Handle ecosystem-specific normalization
        if self.ecosystem == "pypi":
            # Python package names are case-insensitive and use hyphens/underscores interchangeably
            return self.package_name.lower().replace("_", "-")

        return self.package_name.lower()

    def get_search_terms(self) -> list[str]:
        """Get dependency-specific search terms."""
        terms = super().get_search_terms()

        # Add package-specific terms
        terms.append(self.package_name)
        terms.append(self.get_canonical_name())

        if self.replaces:
            terms.extend(self.replaces)

        # Add ecosystem terms
        terms.append(self.ecosystem)

        return list(set(terms))


class FrameworkChoice(TechnicalChoice):
    """A choice about adopting a framework or major architectural library."""

    choice_type: ChoiceType = Field(
        default=ChoiceType.FRAMEWORK, description="Always framework"
    )
    framework_name: str = Field(..., description="Framework name")
    use_case: str = Field(..., description="What this framework will be used for")
    architectural_impact: str = Field(
        ..., description="How this affects the overall architecture"
    )
    migration_required: bool = Field(
        False, description="Whether migration from existing solution is needed"
    )
    current_solution: str | None = Field(
        None, description="What this framework replaces"
    )

    def get_canonical_name(self) -> str:
        """Get canonical framework name."""
        # Common framework name mappings
        mappings = {
            "reactjs": "react",
            "react.js": "react",
            "vuejs": "vue",
            "vue.js": "vue",
            "angular.js": "angularjs",
            "next.js": "nextjs",
            "fast-api": "fastapi",
            "fastapi": "fastapi",
        }

        normalized = self.framework_name.lower().strip()
        return mappings.get(normalized, normalized)

    def get_search_terms(self) -> list[str]:
        """Get framework-specific search terms."""
        terms = super().get_search_terms()

        # Add framework-specific terms
        terms.append(self.framework_name)
        terms.append(self.get_canonical_name())

        if self.current_solution:
            terms.append(self.current_solution)

        # Add use case terms
        import re

        use_case_words = re.findall(r"\b\w+\b", self.use_case.lower())
        terms.extend([word for word in use_case_words if len(word) > 3])

        return list(set(terms))


# Factory function for creating technical choices
def create_technical_choice(
    choice_type: str | ChoiceType, name: str, context: str, **kwargs: Any
) -> TechnicalChoice:
    """Factory function to create the appropriate TechnicalChoice subclass."""

    if isinstance(choice_type, str):
        choice_type = ChoiceType(choice_type.lower())

    if choice_type == ChoiceType.DEPENDENCY:
        # Extract dependency-specific info from kwargs
        return DependencyChoice(
            name=name,
            package_name=kwargs.get("package_name", name),
            context=context,
            ecosystem=kwargs.get("ecosystem", "npm"),  # Default to npm
            version_constraint=kwargs.get("version_constraint"),
            is_dev_dependency=kwargs.get("is_dev_dependency", False),
            replaces=kwargs.get("replaces"),
            alternatives_considered=kwargs.get("alternatives_considered", []),
            metadata=kwargs.get("metadata", {}),
        )

    elif choice_type == ChoiceType.FRAMEWORK:
        return FrameworkChoice(
            name=name,
            framework_name=kwargs.get("framework_name", name),
            context=context,
            use_case=kwargs.get("use_case", context),
            architectural_impact=kwargs.get("architectural_impact", "To be determined"),
            migration_required=kwargs.get("migration_required", False),
            current_solution=kwargs.get("current_solution"),
            alternatives_considered=kwargs.get("alternatives_considered", []),
            metadata=kwargs.get("metadata", {}),
        )

    else:
        # Generic technical choice
        return TechnicalChoice(
            choice_type=choice_type,
            name=name,
            context=context,
            alternatives_considered=kwargs.get("alternatives_considered", []),
            metadata=kwargs.get("metadata", {}),
        )
