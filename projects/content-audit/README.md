# Content Audit: Large-Scale Page Verification System

A multi-agent parallel processing system that audited 1,728 content pages to identify false or misleading claims. Uses 5 parallel agents across 7 processing rounds with web scraping, pattern matching, and false positive analysis.

## Architecture

```
Input: 1,728 URLs (CSV)
    ↓
Split into 7 Rounds (250 URLs each, 210 in final round)
    ↓
┌───────────────────────────────────────────┐
│ Per Round: 5 Parallel Agents (50 URLs each)  │
│ Agent 1: URLs  1-50                           │
│ Agent 2: URLs 51-100                          │
│ Agent 3: URLs 101-150                         │
│ Agent 4: URLs 151-200                         │
│ Agent 5: URLs 201-250                         │
└───────────────────────────────────────────┘
    ↓
Consolidate Results → False Positive Analysis → Reports
```

## The Problem

A product's integration connector was read-only (import only), but some of its 1,728 use-case pages incorrectly suggested write-back functionality existed. This created:
- Misleading claims about bidirectional sync
- False promises of bulk update capabilities
- Incorrect references to data push operations
- Generic testimonials creating ambiguity

## Pipeline Stages

### Stage 1: URL Ingestion
- Load 1,728 URLs from CSV input
- Split into 7 rounds of ~250 URLs each
- Assign 50 URLs per agent per round

### Stage 2: Page Scraping
- **Primary**: Exa AI semantic web search
- **Backup**: Firecrawl API for pages Exa can't access
- Extract full page content for analysis

### Stage 3: Pattern Matching
Scan for critical write-back keywords:
- "push data back", "write back", "two-way sync"
- "bulk update", "bulk edit", "mass update"
- "import to [ERP]", "push to [ERP]"
- "journal entry creation", "purchase order import"
- "bidirectional", "two-way"

### Stage 4: Contextual Analysis
- Distinguish between actual write-back claims and:
  - Generic testimonials (not product-specific)
  - "Export FROM" language (opposite direction)
  - Data preparation descriptions (no automated write-back)
  - SuiteScript/API documentation references

### Stage 5: Result Compilation
- JSON output per agent per round (70+ result files)
- Critical findings extracted to separate text files
- Round summaries with statistics
- Flagged URLs with context and line numbers

### Stage 6: False Positive Analysis
- Cross-reference flagged URLs against ground truth capabilities
- Categorize false positives:
  - Generic testimonial only (80.6% of false positives)
  - Export FROM ERP (12.9%)
  - Data preparation only (6.5%)
- Calculate true critical vs. false positive rates

### Stage 7: Executive Reporting
- Final audit report with statistics
- Verified critical URLs list
- Content segmentation analysis
- Remediation recommendations

## Processing Scale

| Metric | Value |
|--------|-------|
| Total URLs | 1,728 |
| Successfully audited | 1,684 (97.5%) |
| Processing rounds | 7 |
| Agents per round | 5 (parallel) |
| URLs per agent | 50 |
| Total result files | 70+ |

## Results

### Content Quality Segmentation

| Segment | URLs | % of Total | Critical Issues |
|---------|------|------------|----------------|
| Segment A (1-518) | 518 | 30% | 0 (excellent) |
| Segment B (519-1268) | 750 | 43% | 5-11% (mixed) |
| Segment C (1269-1728) | 460 | 27% | 2-4% (good) |

### Findings Summary

- **Raw flagged URLs**: ~239 (14% of content)
- **True critical issues**: 50-100 (3-6% of content)
- **Verified critical**: 26-27 URLs
- **False positive rate**: 53.4% of flagged URLs
- **Clean content**: ~1,500 pages (86%)

### Critical Issue Categories

| Category | Count | Severity |
|----------|-------|----------|
| Journal entry operations | 10-15 | CRITICAL |
| Bulk update operations | 15-20 | CRITICAL |
| Purchase order operations | 5-10 | CRITICAL |
| Bidirectional/two-way sync | 10-20 | MEDIUM-CRITICAL |
| Explicit "push" language | 5-10 | CRITICAL |
| Generic testimonial (false positive) | 100-150 | N/A |

### Root Cause: Generic Testimonial

The primary false positive source was a generic customer testimonial appearing on nearly every page that mentioned "push data back into our systems" — which wasn't specific to the ERP connector but created ambiguity when displayed alongside ERP-specific content. This single testimonial accounted for 80.6% of all false positives.

## Stack

- **Agents**: Claude Code multi-agent (5 parallel agents × 7 rounds)
- **Scraping**: Exa AI (primary), Firecrawl API (backup)
- **Analysis**: Python pattern matching + contextual AI analysis
- **Output**: JSON results, Markdown reports, text summaries

## Key Decisions

1. **5 parallel agents per round** — Processing 1,728 URLs sequentially would be impractical. 5 agents × 50 URLs balances parallelism with manageability.
2. **7 rounds instead of 1 large batch** — Allows checkpoint/resume if a round fails. Each round produces independent results.
3. **False positive analysis as a separate stage** — Raw pattern matching flags too aggressively. Dedicated analysis step filters noise from signal.
4. **Ground truth document** — A capabilities cheat sheet serves as the authoritative source for what the connector actually supports, enabling accurate claim verification.
5. **Content segmentation** — Analyzing results by URL range revealed that content quality varies by segment, focusing remediation effort on the middle segment.

## Visual Direction

**Diagram**: Funnel visualization showing 1,728 URLs entering at the top, splitting into 7 processing rounds, each with 5 parallel agent lanes. Results converge into a filtering stage that separates true critical (red) from false positives (yellow) from clean content (green). Bottom shows the content segmentation map with three segments color-coded by quality. Side panel shows the false positive breakdown pie chart (generic testimonial 80.6%, export FROM 12.9%, data prep 6.5%).
