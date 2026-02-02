# Agent 1: YouTube Research Specialist

## Role
Research YouTube content from Meta ads experts to extract actionable B2B ad creative insights.

## Data Sources
- Expert creators covering Meta ads, B2B marketing, creative strategy
- Filter: 2025 content, Meta ads related, B2B applicable, creative best practices (not metrics/targeting)

## Processing Pipeline
1. **Video Discovery** — Find relevant videos from tracked channels
2. **Metadata Extraction** — Title, date, duration, view count
3. **Transcript Analysis** (Claude) — Extract insights from spoken content via Firecrawl
4. **Visual Analysis** (Gemini) — Analyze ad examples shown in video via CCR routing
5. **B2B Reframing** — Adapt D2C insights for B2B finance audiences
6. **Synthesis** — Aggregate into best practices with evidence chains
7. **Storage** — Write to Google Sheets (structured) + knowledge base (narrative)

## Dual-Analysis Approach
- **Transcript**: Claude Sonnet 4.5 via Firecrawl MCP (95% success rate)
- **Visual**: Gemini via claude-code-router for screenshot/frame analysis
- **Fallback**: If transcript fails, use video metadata + channel context

## Output
- **Google Sheets**: 4 tabs (Video Analysis, Insights, Best Practices, Channel Tracking)
- **Knowledge base**: `meta-ads-best-practices.md` — living document, grows with each video
- **Insight categories**: Hook, Visual, Copy, CTA, Format, Other
- **Quality target**: 10-15 insights per video, high B2B applicability rating

## MCP Tools
- YouTube MCP (video discovery, metadata)
- Firecrawl MCP (transcript extraction — primary)
- Google Sheets MCP (structured data storage)
- Browserbase MCP (fallback for transcript extraction)
