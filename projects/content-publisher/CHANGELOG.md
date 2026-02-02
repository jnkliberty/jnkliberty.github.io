# Changelog

## Anonymized Release (2026-02-02)

### Anonymization
- Removed WordPress credentials and API URLs from `.env`
- Replaced company-specific directory names (`coeff-playbook-*` → `playbook-*`)
- Replaced company-specific ACF field prefixes
- Removed employee names from test fixtures
- Added `.env.example` with placeholder values

### Code Quality Notes
- Dependencies are current stable versions (axios 1.8, jsdom 26, winston 3.17)
- No security issues found (auth uses env vars, no hardcoded credentials in source)
- Worker thread concurrency model is appropriate for CPU-bound HTML parsing
- Error handling at system boundaries (file I/O, API calls) is present
- `mocha` in dependencies (not devDependencies) — minor but not a runtime issue
