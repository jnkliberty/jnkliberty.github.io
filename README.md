# builds

Portable, anonymized versions of projects I've built — GTM automations, AI agent systems, and internal tools.

Each folder is a self-contained project with its own README, architecture notes, and (where possible) runnable code.

## Projects

| Project | What It Does | Stack | Agents |
|---------|-------------|-------|--------|
| [gtm-site](./projects/gtm-site/) | GTM consulting site — booking flow, lead capture, RSS content feed | Next.js, Supabase, Resend, Upstash | — |
| [content-publisher](./projects/content-publisher/) | Automated HTML-to-CMS publishing with screenshot generation and Webflow integration | Node.js, Puppeteer, Webflow API | — |
| [job-change-detection](./projects/job-change-detection/) | LinkedIn profile monitoring pipeline — detects job changes, enriches phone/email, updates CRM | Python, aiohttp, Bright Data, LeadsMagic, Better Contact | — |
| [ai-ad-creative](./projects/ai-ad-creative/) | AI ad creative system — research, brief generation, multi-format output, 34-point editorial review | Claude Code, 4 agents | 4 |
| [personalized-outreach](./projects/personalized-outreach/) | Two-level research + 100-point ICP qualification + messaging validation gates | Claude Code, 5 agents | 5 |
| [reddit-engagement](./projects/reddit-engagement/) | Community engagement across Reddit/Trailblazer — comment context intelligence, sensitivity-adapted responses | Claude Code, 3 agents | 3 |
| [review-intelligence](./projects/review-intelligence/) | Multi-marketplace review collection with progressive fallback scraping and 3-level deduplication | Claude Code, 6 agents | 6 |
| [linkedin-outreach](./projects/linkedin-outreach/) | Personalized outreach at scale — exactly 7-word subjects, 100-150 char openers, dual-version A/B | Claude Code, 3 agents | 3 |
| [content-engine](./projects/content-engine/) | SEO/AEO blog pipeline — 17 comparison posts in one day with 6-phase editorial review | Claude Code, 5 agents | 5 |
| [competitor-monitoring](./projects/competitor-monitoring/) | Connector outage intelligence — multi-source search, AI severity scoring, $0.22/scan | Python, Claude API, Exa, Browserbase, SQLite | — |
| [content-audit](./projects/content-audit/) | 1,728-page content audit — 5 parallel agents × 7 rounds, false positive analysis | Claude Code, 5×7 agents | 35 |
| [finance-tools](./projects/finance-tools/) | 29 blogs + 33 Excel templates (688 fixes) + 33 landing pages + paystub generator app | Python, React, TypeScript, 5 agents | 5 |

## Structure

```
projects/
  gtm-site/                # Next.js consulting site
  content-publisher/        # HTML-to-CMS automation
  job-change-detection/     # LinkedIn job change pipeline (Python)
  ai-ad-creative/           # 4-agent ad creative system
  personalized-outreach/    # 5-agent research + qualification
  reddit-engagement/        # 3-agent community engagement
  review-intelligence/      # 6-agent review collection
  linkedin-outreach/        # 3-agent outreach personalization
  content-engine/           # 5-agent SEO blog pipeline
  competitor-monitoring/    # Outage intelligence (Python)
  content-audit/            # 35-agent parallel content audit
  finance-tools/            # Templates, blogs, apps
```

## About

Built by [Julian Alvarado](https://gtm.run). GTM engineering for B2B SaaS.
