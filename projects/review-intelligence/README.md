# Review Intelligence: Multi-Agent Review Collection Pipeline

A six-agent system that collects, processes, and manages product reviews and competitive intelligence across multiple marketplaces. Features progressive fallback web scraping, multi-level deduplication, and automated Google Sheets insertion.

## Architecture

```
Master Orchestration Agent (coordinates sequential execution)
    ↓
┌──────────────────────────────────────────────┐
│ Data Collection Layer                         │
│ ├── Product Scraper (5 marketplaces, ALL ratings) │
│ ├── Competitor Scraper (marketplace sources, 1-3★) │
│ └── Alternative Sources Scraper (Capterra/Reddit) │
└──────────────────────────────────────────────┘
    ↓
Data Cleaning Agent (normalization + deduplication)
    ↓
Google Sheets Insertion Agent (batch insert + duplicate detection)
```

## Pipeline Stages

### Stage 1: Product Review Collection
- Scrapes ALL ratings from 5 marketplace platforms
- Pre-scraping deduplication check against existing data
- Progressive fallback: Exa Search → Firecrawl → Browserbase
- Platform-specific scraping strategies

### Stage 2: Competitor Review Collection
- Collects only 1-3 star (negative) reviews from 10+ competitor tools
- Strict URL constraints per marketplace
- Browser automation for filtering-restricted platforms

### Stage 3: Alternative Source Collection
- Targets competitors not on traditional marketplaces
- Sources: Capterra, SoftwareAdvice, Reddit
- Reddit sentiment analysis maps posts to 1-3 star scale:
  - 1★: "terrible", "awful", "complete waste"
  - 2★: "disappointing", "doesn't work well"
  - 3★: "okay but...", "has issues"

### Stage 4: Data Cleaning
- Date normalization (handles relative dates: "2 days ago", various formats)
- Rating standardization (text → numeric 1-5 scale)
- Content processing (HTML removal, encoding fixes, truncation at 2000 chars)
- Reviewer name cleaning (anonymous handling, 50-char limit)
- URL validation (HTTPS enforcement, tracking param removal)

### Stage 5: Multi-Level Deduplication
- **Level 1 (Exact)**: URL match, content + name + date match
- **Level 2 (Fuzzy)**: >90% content similarity, same reviewer near-date match
- **Level 3 (Cross-Source)**: Same review appearing in both product and competitor sheets

### Stage 6: Google Sheets Insertion
- Batch processing with exponential backoff for rate limiting
- Always inserts at row 2 (newest first) to keep recent reviews visible
- Pre-insertion deduplication against existing sheet data
- Post-insertion verification with row count validation

## Agent Specs

| Agent | Role | Key Capability |
|-------|------|----------------|
| Master Orchestrator | Pipeline coordinator | Sequential execution, error handling, partial-result acceptance |
| Product Scraper | Own-product review collection | 5-marketplace coverage, all ratings |
| Competitor Scraper | Competitive intelligence | 10+ tools, negative reviews only (1-3★) |
| Alt Sources Scraper | Non-marketplace collection | Capterra, SoftwareAdvice, Reddit sentiment analysis |
| Data Cleaner | Normalization + dedup | 3-level deduplication, date/rating/content standardization |
| Sheets Inserter | Data persistence | Batch insert, row-2 strategy, duplicate prevention |

## Progressive Fallback Tool Strategy

```
Tier 1 (Cost-Effective): Exa Search + Firecrawl
    ↓ (if blocked/restricted)
Tier 2 (Browser Automation): Browserbase
```

- Try primary tools first → detect failure type → use Browserbase only when needed
- Platform-specific preferences (Exa preferred for app stores, Firecrawl for review sites)
- Session reuse for multiple pages from same domain
- Immediate session cleanup to minimize cost

## Data Schema

### Product Reviews (7 columns)
| Column | Type |
|--------|------|
| Review Date | YYYY-MM-DD |
| Rating | 1-5 |
| Review Content | Text |
| Reviewer Name | Text |
| Reviewer Location/Company | Text |
| Marketplace | Standardized name |
| Review Link | URL |

### Competitor Reviews (8 columns)
| Column | Type |
|--------|------|
| Review Date | YYYY-MM-DD |
| Rating | 1-3 only |
| Review Content | Text |
| Reviewer Name | Text |
| Reviewer Location/Company | Text |
| Marketplace | Standardized name |
| Tool | Competitor tool name |
| Review Link | URL |

## Results

- **36 reviews collected** across 4 platforms in initial run
- **80% platform coverage** (4/5 platforms fully accessible)
- **Browserbase breakthrough**: Bypassed cookie consent restrictions on one marketplace, yielding 10 previously inaccessible reviews (38% increase in collection rate)
- High data quality with complete metadata
- Zero duplicates in final dataset

## Stack

- **Agents**: Claude Code multi-agent (6 agents, orchestrated sequential pipeline)
- **Web scraping**: Firecrawl MCP, Exa MCP (primary), Browserbase MCP (fallback)
- **Data storage**: Google Sheets MCP (2-sheet architecture)
- **Community scraping**: Reddit MCP (sentiment-based review extraction)

## Key Decisions

1. **Negative reviews only for competitors** — Collecting 1-3 star reviews provides competitive intelligence on weaknesses without overwhelming data volume.
2. **Progressive fallback over single tool** — Exa/Firecrawl handle 80% of cases cheaply; Browserbase reserved for restricted platforms.
3. **Row-2 insertion strategy** — Newest reviews always at top for visibility. Avoids append-to-bottom which buries recent data.
4. **Reddit sentiment mapping** — Converts freeform community complaints into structured 1-3 star ratings using keyword analysis.
5. **Cross-source deduplication** — Prevents the same review from appearing in both product and competitor sheets.

## Visual Direction

**Diagram**: Layered architecture showing collection layer (3 scrapers) feeding into cleaning layer (normalization + 3-level dedup), then insertion layer (batch processing + row-2 strategy). Side panel shows progressive fallback decision tree (Exa → Firecrawl → Browserbase). Color-coded by marketplace source.
