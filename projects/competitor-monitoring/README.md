# Competitor Connector Outage Intelligence

An agent-based intelligence system that monitors competitor product connectors for outages, issues, and disruptions across multiple sources. Uses AI-powered severity scoring and multi-source validation to identify actionable competitive intelligence.

## Architecture

```
┌────────────────────────────────────────────┐
│ Search Layer (Multi-Source Collection)       │
│ ├── Exa MCP (semantic web/news/forum search)   │
│ ├── Reddit MCP (real-time user complaints)     │
│ ├── Browserbase MCP (marketplace review scraping)│
│ └── Firecrawl MCP (backup web search)          │
└────────────────────────────────────────────┘
                      ↓
┌────────────────────────────────────────────┐
│ Intelligence Layer (AI Analysis)             │
│ ├── Issue Summarizer (1-2 sentence summaries)  │
│ ├── Severity Scorer (HIGH/MEDIUM/LOW + reasoning)│
│ └── Content Filter (exclude docs/tutorials)    │
└────────────────────────────────────────────┘
                      ↓
┌────────────────────────────────────────────┐
│ Data Layer (Storage + Dedup)                  │
│ ├── SQLite (seen issues tracking)              │
│ ├── Date/Content filtering                     │
│ └── Quality validation                         │
└────────────────────────────────────────────┘
                      ↓
┌────────────────────────────────────────────┐
│ Export Layer                                  │
│ └── Google Sheets MCP (structured output)      │
└────────────────────────────────────────────┘
```

## Pipeline Stages

### Stage 1: Multi-Source Search
- **Exa MCP**: Semantic search across web, LinkedIn, forums, news, Twitter
- **Reddit MCP**: Real-time user complaints from relevant subreddits
- **Browserbase MCP**: App marketplace review scraping (ratings + text)
- **Firecrawl MCP**: Backup web/blog coverage search
- Configurable date window (2-60 days back)

### Stage 2: Content Filtering
- Exclude documentation, tutorials, release notes, marketing content
- Date range enforcement
- Relevance scoring via Exa semantic matching
- Engagement metrics (upvotes, comments, replies)

### Stage 3: AI-Powered Analysis
- **Severity scoring**: HIGH / MEDIUM / LOW with detailed reasoning
- **Issue summarization**: 1-2 sentence summaries of each finding
- **Error type classification**: auth, sync, connection, data_loss, performance
- **Status detection**: ONGOING / LIKELY_RESOLVED / UNKNOWN
- **Business impact assessment**: Free-text impact description

### Stage 4: Deduplication
- SQLite database tracks seen issues by URL + date hash
- Prevents re-reporting of known issues across runs
- Persistent across multiple scan sessions

### Stage 5: Export
- 10-column Google Sheets output
- Sorted by severity (HIGH first) then date (newest first)
- Grouped by connector for easy review

## Connector Monitoring

The system monitors 7 competitor connectors across 5 data platforms:
- 2 accounting platform connectors (Google Workspace + Microsoft)
- 1 CRM connector (Google Workspace) [HIGH PRIORITY]
- 1 ERP analytics driver (native)
- 1 marketing connector (Google Workspace) [HIGH PRIORITY]
- 2 data warehouse connectors (Microsoft + Google Workspace)

Each connector has configured:
- Search keywords and patterns
- Marketplace URLs for review scraping
- Relevant subreddits
- Priority level (HIGH/MEDIUM/LOW)

## Output Schema (Google Sheets)

| Column | Content |
|--------|---------|
| Date Found | When the issue was detected |
| Connector Name | Which competitor connector |
| Data Source | Platform affected |
| Issue Description | AI-generated 1-2 sentence summary |
| Source Type | Web / Support / Reddit / Marketplace |
| URL | Link to original source |
| Issue Date | When the issue was reported |
| Severity | HIGH / MEDIUM / LOW |
| Status | ONGOING / LIKELY_RESOLVED / UNKNOWN |
| Notes | Additional context, business impact |

## Python Module Structure

```
src/
├── agents/
│   ├── severity_scorer.py    # Claude-powered severity analysis
│   └── issue_summarizer.py   # Claude-powered summarization
├── processors/
│   ├── deduplicator.py       # SQLite-based duplicate tracking
│   └── formatter.py          # Sheets output formatting
├── searchers/
│   ├── exa_searcher.py       # Exa MCP integration
│   └── reddit_searcher.py    # Reddit MCP integration
└── writers/
    └── sheets_writer.py      # Google Sheets MCP output
```

~1,700 lines of Python across 8 modules.

## Results

**Test Run (Full 7-Connector Scan)**:
- **Cost**: $0.22 total
  - Exa API: $0.17 (9 searches)
  - Browserbase: $0.02 (1 marketplace scrape)
  - Anthropic API: $0.02 (5 AI analyses)
  - Firecrawl: $0.01 (1 search)
  - Reddit + Sheets: $0.00
- **False positive rate**: 0%
- **Content filtering accuracy**: 100%
- **Date filtering accuracy**: 100%
- Successfully identified a major CRM connector outage (48+ hours, 80+ affected instances) with multi-source validation from news, marketplace reviews, and community reports

**Projected monthly cost**: ~$6.60/month (daily) or ~$0.88/month (weekly)

## Stack

- **Language**: Python 3.11
- **AI**: Claude API (severity scoring + summarization)
- **Search**: Exa MCP, Reddit MCP, Firecrawl MCP
- **Scraping**: Browserbase MCP (marketplace reviews)
- **Storage**: SQLite (deduplication), Google Sheets MCP (output)
- **Config**: YAML (connectors + prompts)

## Key Decisions

1. **Multi-source validation over single-source** — Requires corroboration from 2+ sources for HIGH severity. Eliminates false positives from isolated complaints.
2. **AI severity scoring over keyword matching** — Claude analyzes context to distinguish real outages from routine maintenance. Keyword-only approach had too many false positives.
3. **SQLite dedup over in-memory** — Persists across runs, so weekly scans don't re-report known issues.
4. **$0.22/scan cost target** — Designed for daily or weekly automated runs without budget concerns.
5. **YAML-configured connectors** — Adding new competitors requires only a config change, not code changes.

## Visual Direction

**Diagram**: Four horizontal layers (Search → Intelligence → Data → Export) with the 4 search sources feeding into the intelligence layer. Show severity classification (HIGH/MEDIUM/LOW) as color-coded badges. Right side panel shows a sample Google Sheets output with connector names and severity indicators. Bottom shows cost breakdown pie chart ($0.22 total).
