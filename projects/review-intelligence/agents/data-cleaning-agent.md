# Data Cleaning Agent

## Role
Normalization, validation, and deduplication specialist.

## Processing Pipeline

### Date Normalization
- Convert all formats to YYYY-MM-DD
- Handle relative dates ("2 days ago", "last week", "3 months ago")
- Handle international formats (DD/MM/YYYY vs MM/DD/YYYY)
- Default timezone: UTC

### Rating Standardization
- Convert text ratings to numeric (1-5 scale)
- Handle fractional ratings (round to nearest integer)
- Validate range (1-5 for product, 1-3 for competitors)

### Content Processing
- Remove HTML tags and entities
- Fix encoding issues (UTF-8 normalization)
- Truncate >2000 characters with ellipsis
- Remove promotional content injected by platforms
- Reddit-specific: Format as "Post: [title] | Comments: [excerpts]"

### Multi-Level Deduplication

**Level 1: Exact Match**
- Review URL (exact match) — highest confidence
- Content + reviewer name + date (exact match)

**Level 2: Fuzzy Match**
- >90% content similarity using normalized text
- Same reviewer + same rating + same marketplace + date within 3 days

**Level 3: Cross-Source**
- Check if same review appears in both product and competitor sheets
- Keep most complete version when duplicates found

### Quality Filters
- Skip reviews <10 characters
- Flag suspicious patterns (all caps, excessive special chars)
- Remove duplicate reviews (same reviewer + date + content)
- Validate reviewer name against spam patterns
