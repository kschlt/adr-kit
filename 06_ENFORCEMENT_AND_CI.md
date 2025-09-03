# ADR Kit — Enforcement & CI

## Pre-commit
`.pre-commit-config.yaml`
```yaml
repos:
  - repo: local
    hooks:
      - id: adr-validate
        name: ADR validate
        entry: adr-kit validate
        language: system
```

## GitHub Actions
`.github/workflows/adr.yml`
```yaml
name: adr-guardrails
on: [pull_request, push]
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {{ python-version: "3.12" }}
      - run: pip install adr-kit log4brains
      - run: adr-kit validate && adr-kit index --out docs/adr/adr-index.json
      - run: adr-kit render-site
      - uses: actions/upload-artifact@v4
        with:
          name: adr-site
          path: .log4brains/out
```
