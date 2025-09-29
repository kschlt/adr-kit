# Development Scripts

This directory contains development-only scripts for the ADR Kit project.

**⚠️ These scripts are NOT included in the distribution package** - they are only for developers working on ADR Kit itself.

## Available Scripts

### `clean-install.sh`
Clean installation management for development testing.

```bash
# Make executable (first time only)
chmod +x scripts/clean-install.sh

# Usage
scripts/clean-install.sh uninstall   # Remove package only
scripts/clean-install.sh clean       # Remove all artifacts
scripts/clean-install.sh reinstall   # Full clean + reinstall
scripts/clean-install.sh test        # Test installation
```

## Makefile Integration

These scripts are also available through the Makefile:

```bash
make uninstall    # Uses clean-install.sh uninstall
make clean        # Uses clean-install.sh clean
make reinstall    # Uses clean-install.sh reinstall
```

## Why These Scripts Exist

When developing ADR Kit, you need to:

1. **Test fresh installations** - Ensure new changes work from scratch
2. **Clean up development artifacts** - ADR Kit creates working files that shouldn't be committed
3. **Separate development from distribution** - End users don't need these tools

## Development vs Distribution

- **Development** (this repo): Rich tooling, self-testing capability
- **Distribution** (PyPI): Slim package with only runtime code

End users just run `pip install adr-kit` and `pip uninstall adr-kit` - they don't need these development scripts.