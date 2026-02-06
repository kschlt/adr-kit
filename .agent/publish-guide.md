# Publishing ADR Kit to PyPI

## Version Management

Current version: **0.2.6**

Changes in this release:
- Critical fix: Policy validation warnings for ADR creation (MCP)
- Enhanced documentation for constraint extraction
- Fixed version detection bug (semantic comparison)
- Added comprehensive example ADR fixtures

## Publishing Steps

### 1. Ensure version is updated
Already done: `pyproject.toml` version = "0.2.6"

### 2. Clean build artifacts
```bash
make clean
# Or manually:
rm -rf dist/ build/ *.egg-info/
```

### 3. Build distribution packages
```bash
make build
# Or manually:
uv build
# Or with setuptools:
python -m build
```

This creates:
- `dist/adr_kit-0.2.6-py3-none-any.whl` (wheel)
- `dist/adr-kit-0.2.6.tar.gz` (source)

### 4. Verify build contents (optional)
```bash
tar -tzf dist/adr-kit-0.2.6.tar.gz | head -20
unzip -l dist/adr_kit-0.2.6-py3-none-any.whl | head -20
```

### 5. Upload to PyPI
```bash
# Using uv (if available)
uv publish

# Or using twine (traditional)
pip install twine
twine upload dist/*
```

You'll be prompted for PyPI credentials:
- Username: __token__
- Password: <your PyPI API token>

### 6. Verify upload
Visit: https://pypi.org/project/adr-kit/

### 7. Test installation
```bash
# In a different directory/environment
uv tool install adr-kit
# Or
pip install adr-kit

# Verify version
adr-kit --version
# Should show: 0.2.6
```

### 8. Tag release in git
```bash
git tag v0.2.6
git push origin v0.2.6
```

### 9. Users can update with
```bash
uv tool upgrade adr-kit
# Or
pip install --upgrade adr-kit
```

## PyPI API Token Setup

If you don't have a PyPI API token:

1. Go to https://pypi.org/manage/account/token/
2. Create new API token
3. Scope: "Entire account" or "Project: adr-kit"
4. Save token securely (one-time display)
5. Use as password when prompted

## Troubleshooting

### "File already exists"
You can't re-upload the same version. Bump version number.

### "Invalid credentials"
- Check token format: Should start with `pypi-`
- Username must be `__token__` (literal)
- Ensure no extra whitespace in token

### "Package name taken"
First-time upload requires package registration on PyPI.

## Automated Publishing (CI/CD)

For GitHub Actions, add PyPI token as secret:
- Repository Settings → Secrets → Actions
- Add secret: `PYPI_API_TOKEN`
- See `.github/workflows/publish.yml` (if exists)
