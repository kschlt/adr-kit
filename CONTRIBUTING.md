# Contributing to ADR Kit

Thank you for your interest in contributing to ADR Kit.

## Getting Started

**Prerequisites**: Python 3.10+, [uv](https://github.com/astral-sh/uv)

```bash
git clone https://github.com/kschlt/adr-kit.git
cd adr-kit
uv pip install -e ".[dev]"
```

## Development Workflow

### Running Tests

```bash
# Unit tests (fast)
pytest tests/unit/

# All tests
pytest tests/

# With coverage
pytest tests/ --cov=adr_kit
```

### Quality Checks

```bash
ruff check adr_kit/ tests/   # Linting
black adr_kit/ tests/        # Formatting
mypy adr_kit/                # Type checking
```

Or use the Makefile:

```bash
make lint     # ruff + mypy
make format   # black + ruff
make test-all # all tests
```

### MCP Server

ADR Kit's primary interface is an MCP server. To test it manually:

```bash
uv run adr-kit mcp-server
```

Always use `uv run adr-kit` (not a bare `adr-kit`) to ensure you're running the local editable install, not a system-wide version.

**Detailed developer documentation:** See [CLAUDE.md](CLAUDE.md) for comprehensive instructions, including:
- The three versions of ADR Kit (source, local install, system install) and which to use when
- Development workflow (Edit → Test → Verify)
- Testing the MCP server with local changes
- Project structure and what gets packaged vs what's dev-only

## Submitting Changes

1. Fork the repository and create a branch from `main`
2. Make your changes with tests
3. Ensure all quality checks pass (`make lint && make test-all`)
4. Open a pull request against `main`

Please keep PRs focused — one concern per PR. Large refactors should be discussed in an issue first.

## Reporting Issues

Use [GitHub Issues](https://github.com/kschlt/adr-kit/issues). Include:
- ADR Kit version (`adr-kit --version`)
- Python version
- Steps to reproduce
- Expected vs actual behaviour
