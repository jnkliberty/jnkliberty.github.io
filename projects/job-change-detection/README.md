# Job Change Detection Pipeline

Automated pipeline that detects when contacts have changed companies by comparing LinkedIn profile data against CRM records, then enriches new contact information for sales re-engagement.

## What It Does

Monitors a Google Sheets contact list (~6,500 paid users), validates their LinkedIn profiles via Bright Data, detects company changes using fuzzy matching, and enriches job changers with new email addresses and phone numbers using dual-API fallback (Better Contact + LeadsMagic).

Built as an alternative to UserGems ($30K+/year) for a B2B SaaS startup — total API cost under $80.

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Google     │────▶│   LinkedIn   │────▶│  Job Change  │────▶│    Email     │────▶│   Google     │
│   Sheets     │     │  Validation  │     │  Detection   │     │   + Phone   │     │   Sheets     │
│   (input)    │     │  (Bright     │     │  (fuzzy      │     │  Enrichment │     │   (output)   │
│              │     │   Data API)  │     │   matching)  │     │  (dual API) │     │              │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
                                                                      │
                                                               ┌──────┴──────┐
                                                               │             │
                                                          LeadsMagic   Better Contact
                                                          (personal    (B2B work
                                                           mobile)      numbers)
```

## Pipeline Stages

1. **Load Contacts** — Read from Google Sheets via gspread OAuth
2. **Filter** — Skip generic accounts (team@, support@), internal domains, incomplete records
3. **LinkedIn Validation** — Batch fetch profiles via Bright Data API (20 URLs/batch, async polling)
4. **Job Change Detection** — Fuzzy company name matching with:
   - Suffix normalization (Inc, LLC, Ltd, GmbH, etc.)
   - Known alias handling (Google/Alphabet, Facebook/Meta, Twitter/X)
   - SequenceMatcher similarity scoring (threshold: 0.85)
   - Side venture detection (multiple current positions)
5. **Phone Enrichment** — Dual-API fallback:
   - Primary: LeadsMagic Mobile Finder (personal cell phones)
   - Fallback: Better Contact (B2B work numbers)
6. **Email Enrichment** (job changers only) — Dual-API fallback:
   - Primary: Better Contact (email by name + new company)
   - Fallback: LeadsMagic Email Finder
7. **Write Results** — Batch update Google Sheets with validation status, job change flag, new contact info

## Key Features

- **Checkpoint/resume**: JSON-based checkpointing saves progress every batch. Crash-safe with backup files.
- **Bi-directional processing**: Forward (row 1→N) and reverse (row N→1) with separate checkpoint files.
- **New row detection**: Tracks spreadsheet size between runs to auto-detect newly added contacts.
- **Batch recovery**: Failed Google Sheets writes save to JSON for manual recovery.
- **Dry-run mode**: Full pipeline execution without writing to spreadsheet.
- **Re-enrichment**: Separate pass to fill missing emails/phones for previously detected job changers.

## Results

| Metric | Value |
|--------|-------|
| Total contacts processed | 4,932 / 6,487 (76%) |
| Job changers detected | 934 |
| Emails enriched | 519 |
| Phones enriched | 372 |
| LinkedIn profiles validated | 3,419 |
| Total API cost | ~$80 |
| Comparable tool (UserGems) | $30,000+/year |

## Stack

- **Language**: Python 3.11+
- **Async**: aiohttp, asyncio
- **APIs**: Bright Data (LinkedIn), Better Contact (email/phone), LeadsMagic (mobile/email), Google Sheets (gspread)
- **Resilience**: tenacity (retry with exponential backoff)
- **Data**: JSON checkpoints, Google Sheets as primary store

## Key Decisions

- **Google Sheets as database**: The sales team already lived in Sheets. Adding a proper DB would have added complexity without user adoption. Batch updates with retry logic handle the API limits.
- **Dual-API fallback for enrichment**: No single enrichment API has >60% coverage. LeadsMagic excels at personal mobiles; Better Contact at B2B work emails. Running both with fallback gets ~70% coverage.
- **Fuzzy matching over exact**: Company names vary wildly between LinkedIn and CRM records. SequenceMatcher with suffix stripping catches "Google LLC" vs "Alphabet Inc" cases that exact matching misses.
- **Checkpoint per direction**: Forward and reverse processing use separate checkpoint files so both can run independently without state conflicts.

## Visual Direction

> **For designer**: 5-stage horizontal pipeline flow. Each stage is a box with the tool/API underneath. Show the dual-API fallback as a branching path at the enrichment stage. Include a "checkpoint" icon between each stage showing the resume capability. Add a feedback arrow from output back to input showing the re-enrichment loop.
