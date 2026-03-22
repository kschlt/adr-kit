# Security Policy

## Supported Versions

Only the latest release of ADR Kit receives security fixes.

| Version | Supported |
|---------|-----------|
| Latest  | Yes       |
| Older   | No        |

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

To report a vulnerability, please contact the maintainer directly via GitHub: [@kschlt](https://github.com/kschlt). Include:

- A description of the vulnerability and its potential impact
- Steps to reproduce
- Any suggested fixes if you have them

You can expect an acknowledgement within 7 days. We will work with you to understand the issue and coordinate a fix before any public disclosure.

## Scope

ADR Kit is a local developer tool — it reads and writes files in your project directory and runs an MCP server on localhost. It makes no outbound network requests in normal operation (except optional Log4brains site generation). There are no user accounts, authentication systems, or remote data storage.

The most relevant security concerns are:
- Path traversal when reading/writing ADR files
- Command injection via ADR content passed to external tools
- Dependency vulnerabilities in the package supply chain
