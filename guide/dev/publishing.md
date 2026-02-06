# Publishing ADR Kit to PyPI

This guide documents the complete process for publishing new versions of ADR Kit to PyPI.

## Prerequisites

- **PyPI Account**: You need a PyPI account with maintainer access to the `adr-kit` project
- **API Token**: Stored in `~/.pypirc` (already configured)
- **Tools**: `uv` and `twine` installed

## Version Numbering

Follow [Semantic Versioning](https://semver.org/):
- **MAJOR** (X.0.0): Breaking changes to public API
- **MINOR** (0.X.0): New features, backward compatible
- **PATCH** (0.0.X): Bug fixes, backward compatible

Examples:
- `0.2.5` → `0.2.6`: Bug fixes, improvements (patch)
- `0.2.5` → `0.3.0`: New features (minor)
- `0.9.5` → `1.0.0`: Breaking changes or stable release (major)

## Publishing Checklist

### 1. Update Version Number

Edit `pyproject.toml`:
```toml
[project]
name = "adr-kit"
version = "0.X.Y"  # ← Update this
```

### 2. Update Changelog (if exists)

Document what changed in this release:
- New features
- Bug fixes
- Breaking changes
- Deprecations

### 3. Commit Version Bump

```bash
git add pyproject.toml
git commit -m "chore: Bump version to 0.X.Y for release

Release includes:
- feature/fix description 1
- feature/fix description 2"

git push
```

### 4. Clean Build Artifacts

```bash
make clean
```

This removes:
- `dist/` directory
- `build/` directory
- `*.egg-info/` directories
- Cache files

### 5. Build Distribution Packages

```bash
uv build
```

This creates two files in `dist/`:
- `adr_kit-0.X.Y-py3-none-any.whl` (wheel format)
- `adr_kit-0.X.Y.tar.gz` (source distribution)

Verify the build:
```bash
ls -lh dist/
```

### 6. Publish to PyPI

Use the publish helper script:

```bash
./scripts/publish.sh
```

Or manually with environment variables:

```bash
UV_PUBLISH_USERNAME="__token__" \
UV_PUBLISH_PASSWORD=$(grep -A1 '\[pypi\]' ~/.pypirc | grep password | cut -d' ' -f3) \
uv publish
```

If `uv publish` fails, use `twine`:

```bash
uv run twine upload dist/*
```

You should see:
```
Publishing 2 files to https://upload.pypi.org/legacy/
Uploading adr_kit-0.X.Y-py3-none-any.whl
Uploading adr_kit-0.X.Y.tar.gz

View at:
https://pypi.org/project/adr-kit/0.X.Y/
```

### 7. Tag the Release

```bash
git tag v0.X.Y
git push origin v0.X.Y
```

This creates a GitHub release tag that matches the PyPI version.

### 8. Verify Publication

Check PyPI:
```bash
# View the package page
open https://pypi.org/project/adr-kit/

# Check latest version via API
curl -s https://pypi.org/pypi/adr-kit/json | \
  python3 -c "import sys, json; print(json.load(sys.stdin)['info']['version'])"
```

Test installation in a clean environment:
```bash
# In a different directory
uv tool install adr-kit
adr-kit --version  # Should show: 0.X.Y

# Or using pip
pip install adr-kit
python -c "import adr_kit; print(adr_kit.__version__)"
```

### 9. Update Documentation (Optional)

If you maintain a CHANGELOG.md or release notes:
- Update with release details
- Commit and push

## Common Issues & Solutions

### Issue: "File already exists"

**Problem**: You're trying to upload a version that already exists on PyPI.

**Solution**: You cannot replace an existing version. Bump the version number:
- If `0.2.6` exists, use `0.2.7` or `0.3.0`
- Update `pyproject.toml`
- Rebuild: `make clean && uv build`
- Upload again

### Issue: "Invalid credentials"

**Problem**: PyPI authentication failed.

**Solution**: Check `~/.pypirc`:
```bash
cat ~/.pypirc
```

Should contain:
```ini
[distutils]
index-servers = pypi

[pypi]
username = __token__
password = pypi-...
```

If missing, recreate PyPI API token:
1. Go to https://pypi.org/manage/account/token/
2. Create token for "adr-kit" project
3. Update `~/.pypirc` with new token

### Issue: "`uv publish` doesn't find credentials"

`uv publish` doesn't automatically read `~/.pypirc`. Set environment variables:

```bash
export UV_PUBLISH_USERNAME="__token__"
export UV_PUBLISH_PASSWORD=$(grep -A1 '\[pypi\]' ~/.pypirc | grep password | cut -d' ' -f3)
uv publish
```

Or use `twine`:

```bash
uv run twine upload dist/*
```

### Issue: "Package name taken" (first-time publish)

**Problem**: Project name doesn't exist on PyPI yet.

**Solution**:
1. First upload creates the project automatically
2. Ensure you own the package name on PyPI
3. If name is taken, choose a different name in `pyproject.toml`

## Quick Reference

Complete publishing workflow:

```bash
make clean                          # Clean artifacts
vim pyproject.toml                  # Update version to 0.X.Y
git add pyproject.toml
git commit -m "chore: Bump version to 0.X.Y for release"
git push
uv build                            # Build packages
./scripts/publish.sh                # Publish to PyPI
git tag v0.X.Y                      # Tag release
git push origin v0.X.Y              # Push tag
```

Verify publication:

```bash
curl -s https://pypi.org/pypi/adr-kit/json | \
  python3 -c "import sys, json; print(json.load(sys.stdin)['info']['version'])"
```

## Users Updating

After you publish, users can upgrade with:

```bash
# Using uv
uv tool upgrade adr-kit

# Using pip
pip install --upgrade adr-kit
```

The health check in `adr-kit mcp-health` will notify users when updates are available.

## Security Notes

- **Never commit** `~/.pypirc` to version control (contains API token)
- **Regenerate tokens** if they're ever exposed
- **Use project-scoped tokens** when possible (not account-wide)
- **Keep tokens secure** - they grant upload permissions

## Related Files

- `pyproject.toml` - Package metadata and version number
- `~/.pypirc` - PyPI credentials (not in repo)
- `scripts/publish.sh` - Publishing helper script
- `Makefile` - Automation commands (`make clean`, `make build`)

## Rollback

**You cannot delete or replace PyPI releases.** If you publish a broken version:

1. Publish a fixed version with a higher number (e.g., `0.2.7`)
2. Optionally mark the broken version as "yanked" on PyPI:
   - Go to https://pypi.org/project/adr-kit/
   - Click "Manage" → "Releases"
   - Select version → "Yank release"
   - Users can still install it explicitly, but it won't be the default

## Automation (Future)

Consider setting up GitHub Actions for automated publishing:

```yaml
# .github/workflows/publish.yml
name: Publish to PyPI
on:
  release:
    types: [published]
jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: astral-sh/setup-uv@v1
      - run: uv build
      - run: uv run twine upload dist/*
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
```

Then publishing becomes:
1. Create GitHub release with tag `vX.Y.Z`
2. GitHub Actions automatically publishes to PyPI

---

**Last Updated**: 2026-02-06 (v0.2.6 release)
