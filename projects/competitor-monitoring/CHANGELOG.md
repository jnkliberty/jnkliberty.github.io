# Changelog

## Anonymized Release (2026-02-02)

### Anonymization
- Removed Anthropic API key from .env
- Removed Google Sheets ID
- Replaced company name with generic references
- Removed specific competitor connector names and marketplace URLs
- Removed employee name from crontab examples
- Removed sample result JSON files (contained real connector data)
- Kept architecture, Python module structure, and methodology

### Code Quality Notes
- Well-structured modular Python codebase (~1,700 lines)
- YAML configuration for easy connector management
- SQLite deduplication is persistent and efficient
- AI-powered analysis provides contextual severity scoring
- Multi-source validation eliminates false positives
- Cost-optimized: $0.22 per full scan
- Production-tested with 0% false positive rate
