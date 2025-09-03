# ADR Kit — CLI Spec

Binary: `adr-kit`

```
adr-kit init
adr-kit new "Use React Query for data fetching" --tags frontend,data
adr-kit validate [--id ADR-0007]
adr-kit index --out docs/adr/adr-index.json [--sqlite .project-index/catalog.db]
adr-kit supersede ADR-0003 --title "Use React Query for data fetching"
adr-kit export-lint --framework eslint --out .eslintrc.adrs.json
adr-kit render-site  # wraps Log4brains
```

### Exit Codes
- 0 = success
- 1 = validation errors
- 2 = schema errors
- 3 = IO/format errors
