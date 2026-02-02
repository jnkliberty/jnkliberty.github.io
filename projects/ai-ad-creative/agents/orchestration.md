# Agent Orchestration

## Workflow
```
Agent 1 (Research) → Knowledge Base → Agent 2 (Creative) → [User Approval] → Sub-Agents → Agent 3 (Review) → [Approved/Revise]
```

## Communication Matrix
- Agent 1 → Knowledge Base (writes insights + best practices)
- Agent 2 → Reads knowledge base, writes creative briefs + assets
- Agent 3 → Reads assets, writes review reports
- User → Approval gates at brief stage and final review

## Sub-Agent Spawning
- Agent 2 spawns 3 sub-agents via Task tool for parallel asset generation
- Each sub-agent produces V1 (platform) + V2 (AI model) outputs
- Sub-agents share the same knowledge base context

## Filter Logic
- Standard: 2025 content, Meta ads, B2B applicable
- Override: User-provided videos bypass year filter

## Error Handling
- Transcript extraction: Firecrawl primary, Browserbase fallback
- Visual analysis: Gemini via CCR, with retry on routing failures
- Google Sheets: Auth refresh on token expiry
