# Agent 1: Prospect Researcher

## Purpose
Two-level research strategy that enriches prospect data from public sources.

## Two-Level Architecture

### Level 1: Company Intelligence (research once per company)
1. **Company Profile** — Size, industry, location, funding, growth stage
2. **Trigger Hunting** — Automation initiatives, core software migrations, leadership changes, M&A activity
3. **Pain Point Discovery** — Manual workflows, data silos, slow reporting, access bottlenecks
4. **Tech Stack Discovery** — ERP, data warehouse, BI tools, CRM
5. **Persona Identification** — Champions, economic buyers, end users
6. **Use Case Inference** — Map to product's top use cases based on evidence

### Level 2: Individual Intelligence (research per prospect)
- A: LinkedIn profile discovery (5 search strategies)
- B: Career history analysis
- C: Pain point & expertise mining from LinkedIn activity
- D: Activity & engagement research
- E: Tool-specific experience detection
- F: Internal product usage analysis
- G: Persona & champion potential classification
- H: 3 personalization hooks per prospect

## Email Parsing
Handles 5 formats with varying LinkedIn discovery success:
- `firstname.lastname@` — High success
- `firstname_lastname@` — High success
- `f.lastname@` — Medium success
- `firstname@` — Low success (single-name, needs fallback)
- `custom@` — Requires manual review

## LinkedIn Search Strategies (Priority Order)
1. Direct email search on LinkedIn
2. Name + company search
3. Name + domain search
4. Company people list via LinkedIn Scraper
5. Job posting / tech community search

## Data Collection
- 32 fields total (18 company, 14 individual)
- Stored in Google Sheets: Company Intelligence tab + Sheet1 individual rows
- Success target: >80% completeness, 1+ trigger, 2+ pain points, 1 executive, 1+ use case

## MCP Tools
- LinkedIn Scraper MCP (profile discovery, company people lists)
- Firecrawl MCP (web research, company pages)
- Exa MCP (semantic search for triggers and news)
- Google Sheets MCP (data storage and retrieval)
