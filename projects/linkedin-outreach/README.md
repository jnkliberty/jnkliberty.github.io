# LinkedIn Outreach Automation

A three-agent AI system that generates personalized LinkedIn outreach messages at scale. Creates custom subject lines and opening sentences based on prospect LinkedIn headlines, producing two distinct versions per prospect with strict formatting and quality requirements.

## Architecture

```
Agent 1: Planner
    → Parses LinkedIn headlines from Google Sheets
    → Develops dual personalization strategies
    → Coordinates Writer and Reviewer workflow
    ↓
Agent 2: Writer
    → Generates exactly 7-word subject lines
    → Creates 100-150 character opening sentences
    → Produces Version 1 (product context) + Version 2 (pure personalization)
    ↓
Agent 3: Reviewer
    → Technical compliance verification (exact counts)
    → Writing quality assessment
    → Personalization validation
    → Approve or reject with specific feedback
    ↓ (if rejected)
Agent 2: Writer (revision loop)
```

## Pipeline Stages

### Stage 1: Headline Analysis (Planner)
- Reads LinkedIn headlines from Google Sheets
- Identifies key themes, roles, industries, pain points
- Develops two strategies per prospect:
  - **Version 1**: Product-focused (ties headline to solution capabilities)
  - **Version 2**: Pure personalization (headline/role only, zero product mention)
- Assigns tasks to Writer with specific direction

### Stage 2: Content Generation (Writer)
- Generates 4 outputs per prospect:
  - Version 1 Subject Line (exactly 7 words)
  - Version 1 Opening Sentence (100-150 characters, product context)
  - Version 2 Subject Line (exactly 7 words)
  - Version 2 Opening Sentence (100-150 characters, no product mention)
- Adheres to strict writing style: 80-90% one/two-syllable words
- Eliminates marketing jargon ("leverage", "synergy", "innovative", etc.)

### Stage 3: Quality Assurance (Reviewer)
- **Technical check**: Exact word counts (7), exact character ranges (100-150)
- **Quality check**: Language simplicity, forbidden patterns, sentence structure
- **Personalization check**: Uniqueness, relevance to specific headline
- **Context accuracy**: Product capabilities correctly represented (V1 only)
- Provides line-by-line feedback for rejections

## Email Structure

The generated content fits into this template:

```
Hey [firstname],

I came across your profile on LinkedIn and thought I should reach out.

[PERSONALIZED SENTENCE FROM AGENT OUTPUT]

[Rest of email body]
```

## Strict Technical Requirements

| Element | Requirement |
|---------|-------------|
| Subject line | Exactly 7 words (not "up to 7" — precisely 7) |
| Subject line | No ending punctuation, starts with capital letter |
| Opening sentence | 100-150 characters (including spaces and punctuation) |
| Opening sentence | Complete sentence, designed to follow standard intro |
| Version 1 | Must mention product context explicitly |
| Version 2 | Zero product mention anywhere |
| Language | 80-90% one/two-syllable words |

## Forbidden Language Patterns

- "X isn't just about Y" constructions
- "X is more than just Y" phrases
- Rhetorical questions
- Superlatives without proof
- Marketing buzzwords: "cutting-edge", "revolutionary", "game-changer", "leverage", "synergy"
- Vague benefit statements

## Automatic Rejection Triggers

1. Subject line ≠ exactly 7 words
2. Opening sentence outside 100-150 character range
3. Missing product context in Version 1
4. Product mention in Version 2
5. Marketing jargon or buzzwords present
6. Generic/templated content
7. No clear connection to prospect's specific headline

## Google Sheets Integration

| Column | Content |
|--------|---------|
| H (input) | LinkedIn Headlines |
| I (output) | Version 1 Subject Line |
| J (output) | Version 1 Opening Sentence |
| K (output) | Version 2 Subject Line |
| L (output) | Version 2 Opening Sentence |

## Agent Specs

| Agent | Role | Input | Output |
|-------|------|-------|--------|
| Planner | Strategy + orchestration | LinkedIn headlines (Column H) | Personalization strategies for Writer |
| Writer | Content generation | Strategies + headlines | 4 outputs per prospect (2 versions × subject + sentence) |
| Reviewer | Quality gate | Writer output | Approve or reject with feedback |

## Results

- 5 sample prospects processed with complete dual-version outputs (demonstrated)
- 100% character/word count compliance across all samples
- Quality validation passed on all outputs
- Designed for A/B testing: Version 1 vs Version 2 response rates

## Stack

- **Agents**: Claude Code multi-agent (3 agents with revision loop)
- **Data source**: Google Sheets MCP (LinkedIn headline input)
- **Data output**: Google Sheets MCP (4 columns per prospect)

## Key Decisions

1. **Exactly 7 words, not "up to 7"** — Rigid constraint forces conciseness and prevents generic padding. Easier to review at scale when all subject lines are uniform length.
2. **Dual-version approach** — Enables A/B testing of product-mention vs. pure-personalization strategies. Measures whether product context helps or hurts open rates.
3. **Reviewer agent as hard gate** — No content ships without passing all technical and quality checks. Prevents drift toward generic messaging at scale.
4. **80-90% simple words** — Forces conversational tone that reads as human-written, not AI-generated.

## Visual Direction

**Diagram**: Linear flow from Google Sheets (Column H) through Planner → Writer → Reviewer → back to Sheets (Columns I-L). Show the revision loop between Writer and Reviewer. Side panel shows the email template with highlighted insertion point for the generated sentence. Bottom bar shows rejection criteria as a checklist.
