# Reddit & Community Engagement Automation

A three-agent AI system that automates community engagement across Reddit and Salesforce Trailblazer Community. The system collects posts, analyzes product applicability, and generates context-aware responses for human review before posting.

## Architecture

```
Agent 1: Planner-Researcher
    → Collects posts from Reddit/Trailblazer
    → Writes to "Raw Collection" sheet
    ↓
Agent 2: Product Specialist
    → Analyzes each post for product applicability
    → Drafts solution-first responses (3-5 actionable specifics)
    → Writes applicable posts to "Product Analysis" sheet
    → Cleans Raw Collection sheet
    ↓
Agent 3: Analyst & Copywriter
    → Analyzes existing thread comments before refining
    → Classifies thread types and promotional sensitivity
    → Adapts response tone, length, and product positioning
    → Writes context-refined responses to "Final Refined" sheet
```

## Pipeline Stages

### Stage 1: Data Collection (Agent 1)
- Collects posts from 12+ subreddits or Trailblazer topics
- Handles two-stage collection: API-first with Browserbase fallback for truncated content
- Preserves exact post titles and full descriptions
- Detects and fixes truncated posts automatically

### Stage 2: Applicability Analysis (Agent 2)
- Reads posts from Raw Collection sheet
- Analyzes each for product relevance using connector cheat sheets
- Drafts detailed, solution-first responses
- Removes non-applicable posts (mandatory)
- Generates post-mortem with relevance statistics

### Stage 3: Comment Context Intelligence (Agent 3)
- Retrieves and analyzes existing thread comments
- Classifies thread type: ACTIVE_ENGAGED, TECHNICAL_DEEP, CASUAL_BRIEF, PROMOTIONAL_SENSITIVE, SOLUTION_CROWDED, DEAD_THREAD
- Adapts response strategy based on sensitivity:
  - **High sensitivity**: Help first, product second
  - **Medium sensitivity**: Acknowledge + alternative positioning
  - **Low sensitivity**: Direct recommendation
  - **Complex native**: Simpler workaround approach
- Ensures product is mentioned and hyperlinked in every response

## Agent Specs

| Agent | Role | Input | Output | Key Tools |
|-------|------|-------|--------|-----------|
| Planner-Researcher | Data collection lead | Platform, category, date range | Raw Collection sheet | Reddit MCP, Browserbase, Google Sheets MCP |
| Product Specialist | Technical product expert | Raw Collection posts | Product Analysis sheet (applicable only) | Connector cheat sheets, Google Sheets MCP |
| Analyst & Copywriter | Context analysis + refinement | Product Analysis posts + thread comments | Final Refined sheet | Reddit MCP (comments), Google Sheets MCP |

## Key Innovation: Comment Context Intelligence

The system's differentiator is analyzing existing thread comments before generating responses:

1. **Thread tone detection** — casual, professional, technical, humorous
2. **Response length pattern matching** — adapts to community norms
3. **Promotional sensitivity scoring** — prevents downvoted/perceived-promotional content
4. **Existing solution identification** — acknowledges what's already been suggested
5. **OP engagement level assessment** — determines if thread is still active

## Three-Sheet Persistent Pipeline

- **Sheet 1 "Raw Collection"** — Temporary staging, cleaned after each run
- **Sheet 2 "Product Analysis"** — Only applicable posts with drafted responses
- **Sheet 3 "Final Refined"** — Human-reviewable, context-aware responses ready for posting

Each stage produces auditable data with explicit handoffs and verification counts.

## Data Columns (Preserved Across Sheets)

| Column | Description |
|--------|-------------|
| Week | Time period searched |
| Forum | Subreddit or Trailblazer topic |
| Connector | Platform name |
| Topic | Original post title |
| Description | Full post content (no truncation) |
| URL | Direct link |
| Usecase / Integration | Identified use case (Agent 2) |
| AI Draft | Response (drafted by Agent 2, refined by Agent 3) |

## Platform Coverage

**Reddit**: 12+ subreddits across CRM, analytics, accounting, operations, and sales communities

**Trailblazer Community**: Analytics, Reports & Dashboards, Automation, Integration, Data Management topics

## Results

- 100% content completeness (no truncated posts)
- Zero data loss between agents (verified handoffs)
- Thread-appropriate tone matching across all responses
- Promotional sensitivity adaptation based on community patterns
- Human review gate before any content is posted

## Stack

- **Agents**: Claude Code multi-agent (3 agents, sequential pipeline)
- **Data collection**: Reddit MCP, Browserbase MCP (fallback)
- **Data storage**: Google Sheets MCP (3-sheet architecture)
- **Response quality**: Connector cheat sheets (60+ product integrations as reference)

## Key Decisions

1. **Three-sheet architecture over database** — Google Sheets chosen for transparency and human reviewability. Each sheet represents a pipeline stage with explicit handoffs.
2. **Comment analysis before response generation** — Prevents tone-deaf or overly promotional responses by matching community patterns.
3. **Progressive fallback for data collection** — Reddit API first, Browserbase only when content is truncated. Minimizes cost while ensuring completeness.
4. **Mandatory product mention with adaptive strategy** — Product is always mentioned but positioning adapts to thread sensitivity level.

## Visual Direction

**Diagram**: Three-lane swim diagram showing Agent 1 → Agent 2 → Agent 3 flow, with the three Google Sheets as data handoff points between lanes. Side panel shows thread classification types (ACTIVE_ENGAGED through DEAD_THREAD) with corresponding response strategies. Bottom bar shows supported platforms (Reddit subreddits + Trailblazer topics).
