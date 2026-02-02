# GTM Consulting Site

A conversion-optimized consulting site with a multi-step booking flow, lead capture with qualification, and a self-updating content section powered by RSS.

## Stack

- **Framework:** Next.js 15 (App Router, ISR)
- **Database:** Supabase (PostgreSQL + RLS)
- **Email:** Resend (transactional, domain-verified)
- **Rate Limiting:** Upstash Redis
- **Scheduling:** Calendly (inline embed)
- **Content:** Substack RSS (server-side fetch, 1hr ISR revalidation)
- **Hosting:** Vercel

## Architecture

### Booking Flow

```
User visits /book
  → Fills form (name, email, company, automation goal)
  → POST /api/contact (source: booking_form)
  → Rate limit check (5 req/min/IP via Upstash)
  → Zod validation
  → Honeypot check (silent 200 for bots)
  → Save to Supabase leads table (DB rate limit: 3/email/hr)
  → Send notification email via Resend
  → Form fades out → Calendly inline embed appears
  → User picks a time → meeting booked
```

### Lead Magnet Flow

```
User clicks "Get the playbooks" on homepage
  → Email capture modal
  → POST /api/contact (source: resource_form)
  → Two emails sent:
    1. Notification to owner
    2. Playbook hub link to submitter
  → Post-submission qualifier (bottleneck selection)
  → PATCH /api/contact saves qualifier metadata to lead
```

### Content Feed

```
Publish on Substack → tag "lab"
  → Next.js ISR revalidates hourly
  → Server-side RSS fetch (no client JS)
  → Hardcoded fallback if feed unavailable
```

## Security Layers

- Zod schema validation on all inputs
- IP rate limiting (Upstash Redis, 5 req/min)
- DB rate limiting (3 submissions/email/hr via trigger)
- Honeypot field for bot detection
- HTML escaping for XSS prevention
- CSP, HSTS, X-Frame-Options, X-Content-Type-Options via middleware
- Supabase RLS (anon: insert only, authenticated: read)

## Key Decisions

- **Vite → Next.js migration:** Needed API routes, middleware, and SSR. Single repo > separate backend for a consulting site.
- **Cloudflare → Vercel:** Spent 3+ hours debugging Cloudflare Pages incompatibilities with Next.js 15. Vercel deployed first try.
- **Calendly inline vs redirect:** Inline embed inside the glassmorphism card keeps the user on-page. Form → calendar feels like one continuous action.
- **ISR over SSR for content:** Static for users (fast), revalidates in background (fresh). Zero client-side JS for the content section.
