# Content Publisher

Automated content publishing pipeline that transforms structured HTML drafts into WordPress posts with custom blocks, taxonomy, and ACF field data.

## What It Does

Parses HTML files containing structured content (titles, metadata, FAQ blocks, TLDR lists, data tables, embedded media) and publishes them to a WordPress site via the REST API. Handles concurrent extraction with sequential publishing, image resolution from the media library, and file lifecycle management (draft → published).

Built for a B2B SaaS company's content team to publish ~4,800 playbook articles at scale without manual WordPress entry.

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌───────────────────┐
│  HTML Drafts     │────▶│  Extract Workers  │────▶│  Publish Workers  │
│  (structured)    │     │  (concurrent x4)  │     │  (sequential)     │
└─────────────────┘     └──────────────────┘     └───────────────────┘
                              │                          │
                              ▼                          ▼
                        ┌──────────┐              ┌──────────────┐
                        │  JSDOM   │              │  WordPress   │
                        │  Parser  │              │  REST API    │
                        └──────────┘              └──────────────┘
```

## Pipeline Stages

1. **File Discovery** — Scans draft directory for `.html` files
2. **Concurrent Extraction** (4 worker threads) — Parses HTML via JSDOM, extracts:
   - Title, author, description, URL slug
   - Tags and categories (list blocks)
   - TLDR steps (list → ACF repeater block)
   - FAQ (table → ACF question/answer block)
   - Objects/Reports table (table → ACF two-column block)
   - YouTube embeds
   - Images (resolved from WordPress media library by name)
   - Body content (converted to WordPress block editor format)
3. **Sequential Publishing** — For each extracted file:
   - Resolves author ID, tag IDs, category IDs from WordPress
   - Checks for existing post by slug (update vs. create)
   - Posts content with ACF fields, taxonomy, and schema markup
   - Moves published file to `published/` directory

## Stack

- **Runtime**: Node.js 18 (CommonJS)
- **HTML Parsing**: JSDOM
- **Concurrency**: Worker threads (4 concurrent extractors)
- **WordPress API**: Axios with Basic Auth
- **Logging**: Winston (3 loggers: extract, publish, worker)
- **Testing**: Mocha + Chai + Sinon

## Key Decisions

- **Worker threads over async/await**: HTML parsing is CPU-bound; worker threads parallelize extraction across cores while keeping publishing sequential to avoid WordPress race conditions.
- **HTML as source format**: Authors write in Google Docs → export HTML. Custom tag syntax (`post-tag:`, `block:`, `content:image:`) lets authors embed metadata inline without switching tools.
- **ACF field key embedding**: WordPress ACF blocks require internal field keys in the block comment JSON. These are hardcoded from the ACF field group export — fragile but necessary for WordPress's block parser.
- **Image resolution by name**: Images are pre-uploaded to WordPress media library. The pipeline searches by filename during extraction, failing fast if an image is missing rather than publishing broken posts.

## Results

- Published **4,884 playbook articles** across 15+ categories
- **34 posts per batch run** average throughput
- Reduced publishing time from ~15 min/article (manual) to ~30 seconds/article (automated)
- Zero broken posts due to fail-fast image validation

## HTML Syntax Spec

The pipeline accepts HTML with custom semantic tags:

| Tag | Format | Purpose |
|-----|--------|--------|
| `<h1>` | `<h1>Title</h1>` | Post title (required) |
| `<h3>` | `post-tag:author:Name` | Author metadata |
| `<h3>` | `post-tag:url:slug` | URL slug |
| `<h3>` | `post-tag:description:...` | Archive description |
| `<h3>` | `post-tag:tags:` + `<ul>` | Taxonomy tags |
| `<h3>` | `post-tag:categories:` + `<ul>` | Taxonomy categories |
| `<h3>` | `post-tag:schema:{json}` | Schema.org markup |
| `<h3>` | `block:tldr` + `<ul>` | TLDR step list |
| `<h3>` | `block:faq` + `<table>` | FAQ Q&A pairs |
| `<h3>` | `block:objects-reports` + `<table>` | Two-column data table |
| `<h3>` | `block:youtube-embed:URL` | YouTube embed |
| `<h3>` | `content:image:name:alt` | WordPress media image |

## Visual Direction

> **For designer**: Pipeline flow diagram showing HTML files entering extraction workers (parallel), converging into sequential publish queue, with WordPress API as the output. Include the tag parsing step as a sub-process within extraction. Color-code the three phases: discovery (gray), extraction (blue), publishing (green).
