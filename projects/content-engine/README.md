# Content Engine: Multi-Agent SEO Blog Generation Pipeline

A five-agent AI pipeline that produces SEO/AEO-optimized comparison blog posts at scale. The system handles planning, competitive research, writing, editorial review, and publishing — generating 17 long-form comparison articles in a single day.

## Architecture

```
Agent 1: Planner & Orchestrator
    → Determines blog format and positioning strategy
    → Creates comprehensive checklist for each phase
    ↓
Agent 2: Researcher
    → Competitive intelligence and proof point gathering
    → G2 ratings, reviews, customer testimonials
    → Screenshots via Browserbase
    ↓
Agent 3: Writer
    → 3,500-4,500 word blog composition
    → Integrates proof points naturally
    → Follows dynamic positioning strategy
    ↓
Agent 4: Editor
    → 6-phase quality review framework
    → Format, tone, positioning, proof points, balance
    → Publish or revise decision
    ↓ (if revise → back to Agent 3)
Agent 5: Publisher
    → Google Docs creation with professional formatting
    → Hyperlinks, image placeholders, sharing permissions
```

## Pipeline Stages

### Stage 1: Planning (Agent 1)
- Determines blog format:
  - **Format 1**: "Us vs Competitor" (direct comparison)
  - **Format 2**: "Competitor A vs Competitor B" (third-party positioning)
- Analyzes competitor focus (marketing/finance/operations) to set dynamic positioning
- Creates detailed checklist for research, writing, and review phases

### Stage 2: Research (Agent 2)
- Researches competitor products, features, pricing, positioning
- Collects G2 ratings, review excerpts, customer testimonials
- Mines own website for case studies, templates, social proof
- Captures screenshots using Browserbase MCP
- Documents all proof points with sources
- Maintains balanced perspective (competitor strengths AND limitations)

### Stage 3: Writing (Agent 3)
- Writes complete 3,500-4,500 word blog posts
- Maintains conversational, flowing tone (not choppy/bullet-point)
- Integrates proof points naturally throughout
- Applies correct positioning based on competitor type
- Varied sentence structure: 20% short, 50% medium, 30% long

### Stage 4: Editorial Review (Agent 4)
Six-phase quality framework:
1. **Format compliance** — word count, headings, markdown structure
2. **Tone & readability** — conversational test, flow check, context richness
3. **Criticism addressal** — verifies 6 specific quality standards are met
4. **Positioning accuracy** — competitor type alignment, dynamic strategy applied
5. **Proof point verification** — sources, testimonials, G2 ratings present
6. **Balance & credibility** — fair competitor acknowledgment (3+ times)

### Stage 5: Publishing (Agent 5)
- Creates Google Doc with blog title as filename
- Applies professional formatting (headings, bold, lists, links)
- Inserts image placeholders with descriptions
- Adds all hyperlinks on first mention of key terms
- Sets sharing permissions (anyone with link can comment)

## Dynamic Positioning Strategy

Agent 1 determines competitor focus and positions accordingly:

| Competitor Focus | Positioning Strategy |
|-----------------|---------------------|
| Marketing-focused | "Matches marketing capabilities PLUS cross-functional" |
| Finance-focused | Lead with finance superiority and cross-functional advantage |
| Operations-focused | Emphasize operational capabilities first |
| General-purpose | Cross-functional breadth as primary differentiator |

## Quality Standards (Addressing 6 Original Draft Issues)

1. **NO choppy sentences** — Varied structure (1-4 short, 5-10 medium, 15+ long per section)
2. **Rich context** — Explain WHY differences matter, not just WHAT they are
3. **Conversational tone** — Colleague over coffee, not corporate brochure
4. **Balanced perspective** — Acknowledge competitor strengths genuinely (3+ times)
5. **Integrated proof points** — Customer testimonials, G2 ratings, specific data throughout
6. **Finance positioning** — Finance systems/use cases mentioned FIRST, not last

## Blog Formats

### Format 1: Direct Comparison
- Introduction
- What Sets Them Apart
- Head-to-Head: Integrations, Features, UX, Pricing, Support, Security
- The Verdict

### Format 2: Third-Party Comparison
- Introduction
- Competitor 1 Overview
- Competitor 2 Overview
- Head-to-Head: Data Sources, Destinations, Features, UX, Pricing, Performance
- Limitations Both Share
- Why Our Product Is Better (positioned as the alternative)
- The Verdict

## Content Specifications

| Spec | Requirement |
|------|-------------|
| Word count | 3,500-4,500 words |
| Structure | H1 title, H2 sections, H3 subsections |
| Proof points | 3-5 customer testimonials per post |
| G2 data | Specific ratings and review excerpts |
| Screenshots | 5-9 images with alt text and captions |
| Links | First mention of key terms hyperlinked |
| Tone | Conversational, balanced, context-rich |

## Results

- **17 blogs completed** (exceeded 15-blog target)
- **~62,000-76,000 total words** across all posts
- **1-day production timeline** (Oct 9-10, 2025)
- All quality gates passed through editorial review
- All published as Google Docs with shareable links
- **85-153+ screenshots** planned across all posts
- **50+ named customer testimonials** integrated

## Stack

- **Agents**: Claude Code multi-agent (5 agents, sequential with revision loop)
- **Research**: Firecrawl MCP, Exa MCP (competitive intelligence)
- **Screenshots**: Browserbase MCP (browser automation)
- **Publishing**: Google Docs MCP (document creation + formatting)
- **Data**: Google Sheets MCP (authentication and data management)

## Key Decisions

1. **Sequential execution, one blog at a time** — User approval after first blog before proceeding. Catches quality issues early instead of generating 17 posts that all need rework.
2. **Dynamic positioning over static templates** — Competitor type determines how we position ourselves. Marketing competitors get a different angle than finance competitors.
3. **Editor as hard gate with revision loop** — Agent 4 can send back to Agent 3 for revisions. No post publishes without passing all 6 quality phases.
4. **Criticism-driven quality standards** — The 6 quality criteria came from analyzing failures in original draft attempts. Each criterion addresses a specific, documented problem.
5. **Knowledge base as shared context** — Writing guidelines, messaging docs, and format templates ensure consistency across all 17 posts without re-prompting.

## Visual Direction

**Diagram**: Five-stage pipeline with Agent 1-5 as sequential nodes. Show the revision loop between Agent 3 (Writer) and Agent 4 (Editor). Side panel shows the two blog formats as template thumbnails. Bottom section shows the 6 quality criteria as a checklist with pass/fail indicators. Overlay shows 17 blogs flowing through the pipeline with completion status.
