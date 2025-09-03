# Contributing to ADR Kit

Thank you for your interest in contributing to ADR Kit! This document provides guidelines and information for contributors.

## 🚀 Getting Started

### Prerequisites

- Python 3.9 or higher
- Git
- pip

### Development Setup

1. **Fork and clone the repository**
   ```bash
   git clone https://github.com/your-username/adr-kit.git
   cd adr-kit
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install in development mode**
   ```bash
   pip install -e ".[dev]"
   ```

4. **Run tests to ensure everything works**
   ```bash
   pytest tests/
   ```

## 🧪 Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=adr_kit --cov-report=term-missing

# Run specific test file
pytest tests/test_core_model.py

# Run specific test
pytest tests/test_core_model.py::TestADRFrontMatter::test_valid_front_matter
```

### Writing Tests

- Write tests for all new functionality
- Use descriptive test names that explain what is being tested
- Follow the existing test patterns and structure
- Ensure tests are fast and don't depend on external resources

### Test Structure

```
tests/
├── __init__.py
├── test_core_model.py      # Model validation tests
├── test_core_parse.py      # Parsing functionality tests  
├── test_cli.py             # CLI command tests
└── fixtures/               # Test data files
```

## 📝 Code Style

### Python Style Guidelines

- **Formatting**: Use `black` for code formatting
- **Linting**: Use `ruff` for linting
- **Type checking**: Use `mypy` for type checking
- **Import sorting**: Use `ruff` for import organization

### Run code quality checks

```bash
# Format code
black adr_kit/ tests/

# Check linting
ruff check adr_kit/ tests/

# Type checking
mypy adr_kit/

# Run all checks
black adr_kit/ tests/ && ruff check adr_kit/ tests/ && mypy adr_kit/
```

### Code Standards

- Use type hints for all function parameters and return values
- Write comprehensive docstrings for modules, classes, and functions
- Keep functions focused and small
- Use descriptive variable and function names
- Follow existing patterns and conventions

## 🔧 Development Workflow

### Branch Naming

- `feature/description` - New features
- `fix/description` - Bug fixes  
- `docs/description` - Documentation updates
- `refactor/description` - Code refactoring
- `test/description` - Test improvements

### Commit Messages

Follow conventional commit format:

```
type(scope): description

Examples:
feat(cli): add supersede command with relationship updates
fix(parser): handle empty YAML front-matter correctly  
docs(readme): update installation instructions
test(validation): add semantic rule test cases
```

### Pull Request Process

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Write code following the style guidelines
   - Add tests for new functionality
   - Update documentation as needed

3. **Run the test suite**
   ```bash
   pytest
   black adr_kit/ tests/
   ruff check adr_kit/ tests/
   mypy adr_kit/
   ```

4. **Commit your changes**
   ```bash
   git commit -m "feat(scope): description of your changes"
   ```

5. **Push and create pull request**
   ```bash
   git push origin feature/your-feature-name
   ```

6. **Create pull request on GitHub**
   - Use the pull request template
   - Include a clear description of changes
   - Reference any related issues

### Pull Request Guidelines

- **Title**: Clear and descriptive
- **Description**: Explain what changes were made and why
- **Tests**: Include tests for new functionality
- **Documentation**: Update docs for user-facing changes
- **Breaking changes**: Clearly document any breaking changes

## 🐛 Bug Reports

When filing bug reports, please include:

- **Python version** and operating system
- **ADR Kit version** (`adr-kit --version`)
- **Minimal example** that reproduces the issue
- **Expected behavior** vs actual behavior
- **Full error message** and stack trace if applicable

## 💡 Feature Requests

For feature requests, please include:

- **Use case**: Describe the problem you're trying to solve
- **Proposed solution**: Your ideas for how it could work
- **Alternatives**: Other approaches you've considered
- **Examples**: Show how the feature would be used

## 📖 Documentation

### Types of Documentation

- **README**: Overview and quick start guide
- **API docs**: Function and class documentation
- **Examples**: Practical usage examples
- **Tutorials**: Step-by-step guides

### Documentation Guidelines

- Keep documentation up to date with code changes
- Use clear, concise language
- Include practical examples
- Test code examples to ensure they work

## 🎯 Areas for Contribution

### Good First Issues

- Adding more lint rule extractors
- Improving error messages
- Adding validation rules
- Writing documentation examples
- Adding test cases

### Advanced Contributions

- Performance optimizations
- New export formats
- Enhanced MCP server functionality
- Integration with other tools
- Advanced querying capabilities

## 📞 Getting Help

- **GitHub Issues**: For bugs and feature requests
- **GitHub Discussions**: For questions and general discussion
- **Code Review**: Ask for feedback on your pull requests

## 🏆 Recognition

Contributors will be recognized in:

- `CONTRIBUTORS.md` file
- Release notes for significant contributions
- GitHub contributor insights

Thank you for contributing to ADR Kit! 🎉