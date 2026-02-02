# Personalized Outreach System

Five-agent AI pipeline that enriches prospect data from public sources, qualifies leads against an ICP framework, and generates personalized multi-channel campaigns — with messaging validation gates between every agent.

## What It Does

Takes a Google Sheet of prospect names/emails, enriches each with company intelligence and individual research, scores them against a 100-point qualification framework, then designs and produces personalized outreach campaigns. Every agent output is validated against a messaging guide (>80 score required to proceed).

Built for a B2B SaaS startup targeting mid-market finance teams (~100-300 employees).

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Agent 1    │────▶│   Agent 2    │────▶│   Agent 3    │────▶│   Agent 4    │────▶│   Agent 5    │
│  Researcher  │     │   Analyst    │     │  Strategist  │     │   Creator    │     │   Editor     │
│              │     │              │     │              │     │              │     │              │
│ Enrich from  │     │ Qualify &    │     │ Design       │     │ Produce      │     │ Review &     │
│ public       │     │ score        │     │ campaign     │     │ assets       │     │ approve      │
│ sources      │     │ prospects    │     │ strategy     │     │              │     │              │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │                    │                    │                    │                    │
       ▼                    ▼                    ▼                    ▼                    ▼
   Messaging            Messaging            Messaging            Messaging            Messaging
   Validation           Validation           Validation           Validation           Validation
   Gate (>80)           Gate (>80)           Gate (>80)           Gate (>80)           Gate (>80)
```

## Pipeline Stages

### Agent 1: Researcher
Enriches prospect data from public sources using a two-level architecture:

**Company-level** (researched once per company, shared across prospects):
- Company profile (size, industry, funding, growth stage)
- Trigger hunting (automation initiatives, migrations, leadership changes, M&A)
- Pain point discovery (manual workflows, data silos, slow reporting, access bottlenecks)
- Tech stack discovery (ERP, data warehouse, BI, CRM)
- Persona identification (champions, economic buyers, users)
- Use case inference (mapped to product's top 8 use cases)

**Individual-level** (researched per prospect):
- LinkedIn profile discovery (5 search strategies with fallback)
- Career history analysis
- Pain point & expertise mining from LinkedIn activity
- Internal product usage data analysis
- Persona classification and champion potential scoring
- 3 personalization hooks per prospect

**Tools**: LinkedIn Scraper MCP, Firecrawl MCP, Exa MCP, Google Sheets MCP

### Agent 2: Analyst
Qualifies prospects against ICP using Agent 1's research:

**100-point scoring framework**:
| Category | Points | What's Measured |
|----------|--------|----------------|
| Company Fit | 40 | Employee count, industry, tech stack |
| Trigger Quality | 20 | Leadership changes, funding, migration, M&A |
| Pain Alignment | 20 | Direct quotes vs inferred pain |
| Individual Fit | 20 | Persona quality + product engagement |

**Score tiers**: 90-100 (HOT), 80-89 (WARM), 70-79 (QUALIFIED), 60-69 (MARGINAL), <60 (DEPRIORITIZE)

**Also produces**: Use case assignment, benefit pillar mapping, competitive context, outreach strategy recommendation

### Agent 3: Strategist (Planned)
- Designs multi-channel campaign strategy based on qualification tier
- Selects channels, sequences, timing, and messaging angles
- Maps content to funnel stage and persona

### Agent 4: Creator (Planned)
- Produces actual marketing assets (emails, ads, landing pages)
- Personalizes based on Agent 1 research + Agent 2 qualification + Agent 3 strategy

### Agent 5: Editor (Planned)
- Reviews all assets for quality, brand compliance, and messaging alignment
- Final approval gate before outreach execution

## Key Features

- **Two-level data architecture**: Company intelligence researched once and shared across all prospects at that company. Prevents redundant API calls and ensures consistency.
- **Messaging validation gates**: Every agent transition scored against messaging guide (>80 required). Catches misalignment early before downstream agents waste work.
- **Email parsing intelligence**: Handles 5 email formats (firstname.lastname, firstname_lastname, f.lastname, firstname@, etc.) with varying success rates for LinkedIn discovery.
- **5 LinkedIn search strategies**: Cascading fallback from email search → name+company → domain search → company people list → job posting analysis.
- **Internal usage signals**: Incorporates product usage data (login frequency, feature adoption) to distinguish active users from cold prospects — changes outreach from cold pitch to expansion play.

## Results (Agents 1-2 Live Test)

| Metric | Value |
|--------|-------|
| Company research completeness | 90/100 |
| Individual qualification accuracy | 74/100 (QUALIFIED tier) |
| Messaging validation score | 97/100 |
| Data fields enriched per prospect | 32 (18 company + 14 individual) |
| Time savings vs manual | 65-95 min → 6-10 min per prospect |
| System completion | 40% (Agents 1-2 done, 3-5 planned) |

## Stack

- **Language**: Python 3.11+
- **Orchestrator**: Claude Sonnet 4.5
- **Data**: Google Sheets (primary store) + Markdown (knowledge base)
- **MCP servers**: LinkedIn Scraper, Firecrawl, Exa, Google Sheets, Google Docs, Mem0
- **Libraries**: pandas, asyncio

## Key Decisions

- **Two-level over flat architecture**: A flat approach re-researches the same company for every prospect. The two-level approach (Company Intelligence tab + individual rows) researches each company once, saving 15-20 min per duplicate.
- **Messaging validation gates over end-of-pipeline review**: Catching messaging misalignment at Agent 1 is cheaper than discovering it at Agent 5. Each gate adds ~30 seconds but prevents hours of wasted downstream work.
- **100-point scoring over binary qualify/disqualify**: Granular scoring enables prioritization within qualified prospects and reveals which dimension (company fit, triggers, pain, individual) is weakest — informing outreach strategy.
- **Internal usage data as signal**: Discovering a prospect is an active user completely changes the outreach approach (expansion vs. cold). This single signal had the highest impact on campaign strategy.

## Visual Direction

> **For designer**: 5-agent horizontal pipeline with messaging validation gates shown as checkpoints between each agent. The two-level data architecture should be visualized as a shared "Company Intelligence" layer underneath the individual prospect flow. Show the 100-point scoring breakdown as a stacked bar chart in Agent 2's section.
