# AI Ad Creative System

Multi-agent system that researches Meta ad best practices from YouTube creators, then generates production-ready B2B ad creative with dual-version output (UI platform + AI model prompts).

## What It Does

Built for a B2B SaaS startup targeting mid-market finance teams. Four specialized Claude agents collaborate to research ad creative patterns, generate campaign briefs, produce ad assets, and enforce quality standards. The system created 3 approved campaigns with 18 ad creatives each, all grounded in 160 research insights extracted from expert YouTube content.

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Agent 1    │────▶│   Agent 2    │────▶│   Agent 3    │────▶│   Agent 4    │
│  Researcher  │     │   Creative   │     │   Editor     │     │   Analyst    │
│              │     │              │     │              │     │  (planned)   │
│ YouTube →    │     │ Brief-first  │     │ 34-point     │     │ Performance  │
│ Insights →   │     │ workflow →   │     │ review →     │     │ feedback     │
│ Best         │     │ Dual-version │     │ Approval     │     │ loop         │
│ Practices    │     │ assets       │     │ gate         │     │              │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
        │                    │                    │
        ▼                    ▼                    ▼
   Knowledge Base      Sub-Agents           Review Report
   (160 insights,      (Video, Static,     (34-point score,
    38 best            Infographic          ≥31/34 to
    practices)         specialists)          approve)
```

## Agent Specifications

### Agent 1: Researcher
- **Role**: YouTube content research specialist for B2B Meta ads
- **Sources**: 4 expert creators (Dara Denney, Denis Shatalin, Alex Cooper, Mr. Paid Social)
- **Method**: Dual-analysis (Claude for transcripts via Firecrawl, Gemini for visual analysis)
- **Output**: Living knowledge base with categorized insights (Hook, Visual, Copy, CTA, Format)
- **Results**: 160 insights extracted, 38 synthesized best practices, 3 videos analyzed
- **Tools**: YouTube MCP, Firecrawl MCP, Google Sheets MCP

### Agent 2: Creative
- **Role**: Research-integrated creative director
- **Workflow**: Brief-first with user approval gates before asset generation
- **Sub-agents**: 3 specialists (Video Script, Static Ad, Infographic/Motion) run in parallel
- **Output**: Dual-version system:
  - V1: Formatted for ad platform UI (adcreative.ai)
  - V2: AI model prompts (GPT Image, Veo 3, Gemini)
- **Key feature**: Reads ALL 160 insights + 38 best practices before every brief, maps benefits to specific tactics with citations

### Agent 3: Editor-in-Chief
- **Role**: Quality control and brand compliance gatekeeper
- **Framework**: 6-phase review (Quick scan → Best practices → Messaging → Brand → Production → Connector → Research alignment)
- **Scoring**: 34-point system across 6 sections, ≥31/34 (90%) required for approval
- **Output**: Structured review report with specific, actionable feedback

### Agent 4: Analyst (Planned)
- **Role**: Performance monitoring and optimization feedback loop
- **Would**: Feed performance data back to Agent 1 to refine best practices

## Key Features

- **Brief-first workflow**: User approves creative brief BEFORE any asset generation (prevents wasted work)
- **Research grounding**: Every creative decision cites specific insights (e.g., "BP_001: Statistics-Based Messaging")
- **Dual-version output**: Every asset in 2 formats — platform UI workflows + AI model prompts
- **Parallel sub-agents**: 3 asset specialists run concurrently (45 min → 15-20 min)
- **Knowledge base**: Living document that grows with each video analyzed
- **Messaging compliance**: Finance-specific messaging guide enforced at every stage

## Results

| Metric | Value |
|--------|-------|
| Videos analyzed | 3 (primary) + 2 creator catalogs |
| Total insights extracted | 160 |
| Best practices synthesized | 38 |
| Campaigns created | 3 |
| Approval scores | 100%, 100%, 93% |
| Ad creatives per campaign | 18 (3 concepts × 3 sizes × 2 versions) |
| Review pass rate | 100% (all 3 approved) |

## Stack

- **Orchestrator**: Claude Sonnet 4.5
- **Sub-agents**: Spawned via Task tool for specialized asset generation
- **Video analysis**: Claude (transcripts) + Gemini (visuals) via CCR routing
- **Data**: Google Sheets (structured) + Markdown knowledge base (narrative)
- **MCP servers**: YouTube, Firecrawl, Google Sheets, Browserbase, Google Docs
- **AI tools**: adcreative.ai (V1), GPT Image/Veo 3 (V2)

## Key Decisions

- **Brief-first over asset-first**: Early sessions showed users rejected 60%+ of assets. Adding a brief approval gate before generation eliminated rework.
- **Dual-version output**: Not all teams have access to the same tools. V1 (platform UI) works for marketing teams; V2 (AI prompts) works for technical teams.
- **YouTube as research source**: Expert creators compress months of testing into 15-minute videos. Extracting their patterns via transcript + visual analysis is faster than running tests.
- **34-point scoring over subjective review**: Quantified review criteria eliminated disagreements about "good enough" — either it passes 31/34 or it doesn't.
- **Living knowledge base over static rules**: The best practices file grows with each video analyzed. Agent 2 reads ALL of it before every brief, so new research automatically improves output.

## Visual Direction

> **For designer**: 4-agent horizontal flow diagram with the knowledge base as a shared resource underneath. Show the brief-first approval gate between Agent 2's brief and asset generation. Include the 3 parallel sub-agents branching from Agent 2. Highlight the 34-point scoring system in Agent 3's box.
