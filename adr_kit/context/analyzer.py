"""Task analyzer for understanding what agents are trying to accomplish."""

import re
from enum import Enum
from pathlib import Path

from .models import TaskHint


class TaskType(str, Enum):
    """Types of tasks that agents commonly work on."""

    FEATURE = "feature"  # Adding new functionality
    BUGFIX = "bugfix"  # Fixing existing issues
    REFACTOR = "refactor"  # Improving existing code structure
    DEPENDENCY = "dependency"  # Adding/updating dependencies
    CONFIGURATION = "config"  # Changing configuration
    DOCUMENTATION = "docs"  # Documentation changes
    TESTING = "testing"  # Adding/updating tests
    DEPLOYMENT = "deployment"  # Deployment-related changes
    MIGRATION = "migration"  # Data or code migrations
    INTEGRATION = "integration"  # Integrating with external services
    UI_UX = "ui_ux"  # User interface/experience changes
    PERFORMANCE = "performance"  # Performance optimizations
    SECURITY = "security"  # Security improvements
    MAINTENANCE = "maintenance"  # General maintenance tasks
    EXPLORATION = "exploration"  # Research/proof of concept
    OTHER = "other"  # Catch-all for other tasks


class TaskContext:
    """Analyzed context about what the agent is trying to accomplish."""

    def __init__(
        self,
        task_description: str,
        task_type: TaskType,
        technologies: set[str],
        file_patterns: set[str],
        keywords: set[str],
        priority_indicators: list[str],
        complexity_indicators: list[str],
    ):
        self.task_description = task_description
        self.task_type = task_type
        self.technologies = technologies
        self.file_patterns = file_patterns
        self.keywords = keywords
        self.priority_indicators = priority_indicators
        self.complexity_indicators = complexity_indicators

    @property
    def estimated_priority(self) -> str:
        """Estimate task priority based on indicators."""
        critical_words = ["critical", "urgent", "emergency", "production", "security"]
        high_words = ["important", "asap", "soon", "deadline", "required"]

        description_lower = self.task_description.lower()

        if any(word in description_lower for word in critical_words):
            return "critical"
        elif any(word in description_lower for word in high_words):
            return "high"
        elif self.priority_indicators:
            return "medium"
        else:
            return "low"

    @property
    def estimated_complexity(self) -> str:
        """Estimate task complexity based on indicators."""
        complex_words = [
            "refactor",
            "migrate",
            "integrate",
            "architecture",
            "framework",
        ]
        simple_words = ["fix", "update", "add", "simple", "quick"]

        description_lower = self.task_description.lower()

        if any(word in description_lower for word in complex_words):
            return "high"
        elif any(word in description_lower for word in simple_words):
            return "low"
        else:
            return "medium"

    def get_architectural_scope(self) -> list[str]:
        """Determine what architectural areas this task might affect."""
        scope = []

        # Frontend indicators
        if any(
            tech in self.technologies
            for tech in ["react", "vue", "angular", "frontend", "ui", "component"]
        ):
            scope.append("frontend")

        # Backend indicators
        if any(
            tech in self.technologies
            for tech in ["api", "server", "backend", "database", "service"]
        ):
            scope.append("backend")

        # Data indicators
        if any(
            tech in self.technologies
            for tech in ["database", "sql", "nosql", "data", "migration"]
        ):
            scope.append("data")

        # Integration indicators
        if any(
            tech in self.technologies
            for tech in ["api", "webhook", "integration", "service", "external"]
        ):
            scope.append("integration")

        # Infrastructure indicators
        if any(
            tech in self.technologies
            for tech in ["deploy", "ci", "docker", "kubernetes", "aws", "cloud"]
        ):
            scope.append("infrastructure")

        return scope if scope else ["general"]


class TaskAnalyzer:
    """Analyzes task descriptions to understand architectural relevance."""

    def __init__(self) -> None:
        # Technology patterns
        self.tech_patterns = {
            # Frontend
            "react": ["react", "jsx", "component", "hook", "react-query"],
            "vue": ["vue", "vuejs", "vue.js", "nuxt"],
            "angular": ["angular", "ng", "typescript"],
            "frontend": ["frontend", "ui", "ux", "css", "html", "javascript"],
            # Backend
            "node": ["node", "nodejs", "express", "fastify", "koa"],
            "python": ["python", "django", "flask", "fastapi", "py"],
            "java": ["java", "spring", "springboot"],
            "go": ["go", "golang", "gin"],
            "backend": ["backend", "server", "api", "service"],
            # Database
            "sql": ["sql", "postgres", "mysql", "sqlite", "database"],
            "nosql": ["mongo", "redis", "cassandra", "dynamodb", "nosql"],
            "database": ["database", "db", "schema", "migration", "query"],
            # Cloud/Infrastructure
            "aws": ["aws", "s3", "ec2", "lambda", "cloudformation"],
            "docker": ["docker", "container", "dockerfile", "compose"],
            "kubernetes": ["k8s", "kubernetes", "helm", "deployment"],
            # Tools
            "testing": ["test", "jest", "pytest", "junit", "spec"],
            "build": ["webpack", "vite", "rollup", "build", "bundle"],
            "ci": ["ci", "cd", "github", "gitlab", "jenkins", "deploy"],
        }

        # Task type patterns
        self.task_type_patterns = {
            TaskType.FEATURE: [
                r"implement|add|create|build|develop",
                r"new feature|feature.*add|add.*feature",
                r"functionality|capability",
            ],
            TaskType.BUGFIX: [
                r"fix|bug|issue|problem|error",
                r"broken|not working|failing",
                r"resolve.*issue",
            ],
            TaskType.REFACTOR: [
                r"refactor|restructure|reorganize",
                r"improve.*structure|clean.*code",
                r"optimize.*code",
            ],
            TaskType.DEPENDENCY: [
                r"add.*dependency|install.*package",
                r"upgrade.*version|update.*library",
                r"npm install|pip install|add.*library",
            ],
            TaskType.CONFIGURATION: [
                r"configure|config|setup|settings",
                r"environment|env.*var",
                r"\.config\.|\.json|\.yaml|\.env",
            ],
            TaskType.TESTING: [
                r"test|testing|spec|unittest",
                r"coverage|jest|pytest",
                r"add.*test|test.*add",
            ],
            TaskType.DEPLOYMENT: [
                r"deploy|deployment|release",
                r"production|staging|environment",
                r"ci.*cd|pipeline",
            ],
            TaskType.INTEGRATION: [
                r"integrate|integration|connect",
                r"api.*integration|third.*party",
                r"external.*service|webhook",
            ],
            TaskType.UI_UX: [
                r"ui|ux|interface|design",
                r"component|layout|styling",
                r"user.*interface|user.*experience",
            ],
            TaskType.PERFORMANCE: [
                r"performance|optimize|speed",
                r"slow|latency|memory",
                r"cache|caching",
            ],
        }

    def analyze_task(self, task_hint: TaskHint) -> TaskContext:
        """Analyze a task hint to understand architectural context."""
        description = task_hint.task_description.lower()

        # Detect technologies
        technologies = self._extract_technologies(
            description, task_hint.technologies_mentioned or []
        )

        # Detect task type
        task_type = self._classify_task_type(description, task_hint.task_type)

        # Extract file patterns
        file_patterns = self._extract_file_patterns(task_hint.changed_files or [])

        # Extract keywords
        keywords = self._extract_keywords(description)

        # Detect priority/complexity indicators
        priority_indicators = self._extract_priority_indicators(description)
        complexity_indicators = self._extract_complexity_indicators(description)

        return TaskContext(
            task_description=task_hint.task_description,
            task_type=task_type,
            technologies=technologies,
            file_patterns=file_patterns,
            keywords=keywords,
            priority_indicators=priority_indicators,
            complexity_indicators=complexity_indicators,
        )

    def _extract_technologies(
        self, description: str, mentioned_techs: list[str]
    ) -> set[str]:
        """Extract mentioned technologies from task description."""
        technologies: set[str] = set()

        # Add explicitly mentioned technologies
        technologies.update(tech.lower() for tech in mentioned_techs)

        # Pattern matching for technologies
        for category, patterns in self.tech_patterns.items():
            for pattern in patterns:
                if pattern in description:
                    technologies.add(category)
                    technologies.add(pattern)  # Add specific tech too

        # Look for package names (simple heuristic)
        import_patterns = [
            r"import\s+([a-zA-Z0-9_-]+)",
            r"from\s+([a-zA-Z0-9_.-]+)",
            r"require\(['\"]([a-zA-Z0-9@/_-]+)['\"]",
            r"install\s+([a-zA-Z0-9@/_-]+)",
            r"use\s+([a-zA-Z0-9_-]+)",
        ]

        for pattern in import_patterns:
            matches = re.findall(pattern, description, re.IGNORECASE)
            technologies.update(match.lower() for match in matches)

        return technologies

    def _classify_task_type(
        self, description: str, explicit_type: str | None
    ) -> TaskType:
        """Classify the type of task based on description."""

        # Use explicit type if provided and valid
        if explicit_type:
            try:
                return TaskType(explicit_type.lower())
            except ValueError:
                pass

        # Pattern matching
        for task_type, patterns in self.task_type_patterns.items():
            for pattern in patterns:
                if re.search(pattern, description, re.IGNORECASE):
                    return task_type

        return TaskType.OTHER

    def _extract_file_patterns(self, changed_files: list[str]) -> set[str]:
        """Extract patterns from changed files."""
        patterns = set()

        for file_path in changed_files:
            path = Path(file_path)

            # File extensions
            if path.suffix:
                patterns.add(f"*{path.suffix}")

            # Directory patterns
            if len(path.parts) > 1:
                patterns.add(f"{path.parts[0]}/*")

            # Specific file types
            if path.suffix in [".js", ".jsx", ".ts", ".tsx"]:
                patterns.add("javascript")
            elif path.suffix in [".py"]:
                patterns.add("python")
            elif path.suffix in [".java"]:
                patterns.add("java")
            elif path.suffix in [".go"]:
                patterns.add("go")
            elif path.suffix in [".sql"]:
                patterns.add("database")
            elif path.suffix in [".yml", ".yaml"]:
                patterns.add("config")
            elif path.suffix in [".md"]:
                patterns.add("docs")

        return patterns

    def _extract_keywords(self, description: str) -> set[str]:
        """Extract important keywords from task description."""
        # Remove common stop words and extract meaningful terms
        stop_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "have",
            "has",
            "had",
            "will",
            "would",
            "could",
            "should",
            "can",
            "may",
            "might",
            "this",
            "that",
            "these",
            "those",
            "i",
            "we",
            "you",
            "he",
            "she",
            "it",
            "they",
        }

        # Extract words (3+ characters, not stop words)
        words = re.findall(r"\b[a-zA-Z]{3,}\b", description.lower())
        keywords = {word for word in words if word not in stop_words}

        return keywords

    def _extract_priority_indicators(self, description: str) -> list[str]:
        """Extract priority indicators from description."""
        priority_words = [
            "urgent",
            "critical",
            "asap",
            "immediately",
            "emergency",
            "important",
            "high priority",
            "deadline",
            "soon",
            "quickly",
        ]

        found = []
        for word in priority_words:
            if word in description:
                found.append(word)

        return found

    def _extract_complexity_indicators(self, description: str) -> list[str]:
        """Extract complexity indicators from description."""
        complexity_words = [
            "refactor",
            "architecture",
            "migrate",
            "complex",
            "integration",
            "framework",
            "system",
            "multiple",
            "across",
            "entire",
            "major",
        ]

        found = []
        for word in complexity_words:
            if word in description:
                found.append(word)

        return found
