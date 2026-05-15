# Real Estate Deal Finder Agent

A scheduled Python agent that monitors Israeli apartment listings through real API-based Apify Actors, filters listings by configurable search profiles, scores potential deals, stores history in SQLite, detects new listings and price drops, and sends a daily email report.

This version is **API-only**. It does not use demo data, static listings, or HTML scraping inside this repository.

## Free-safe mode

The default configuration is designed for private low-volume use on the Apify Free plan:

- No credit card is required for Apify Free plan signup.
- The project uses a $5 monthly budget guard by default.
- The project attempts to set Apify's own monthly platform hard limit to $5.
- The project also checks monthly Apify usage before each Actor run.
- If the safe budget is reached, collection stops and the daily report contains a warning instead of running more Actors.
- Default source limits are low: `maxItems: 5` per source.

See `docs/APIFY_FREE_SAFE_SETUP.md` for the detailed setup.

## What it does

- Connects to Yad2 and Madlan through Apify Actors.
- Supports multiple search profiles from one YAML file.
- Filters by city, rooms, price, size, neighborhoods, floor, keywords, and amenities.
- Supports investment-style searches such as apartments that mention they are already rented.
- Calculates price per square meter.
- Scores listings as potential deals.
- Stores seen listings in SQLite to avoid duplicate emails.
- Detects price drops.
- Sends daily reports by console, SMTP, or Gmail API.
- Runs locally, in Docker, or on a GitHub Actions schedule.

## Architecture

```text
GitHub Actions / local cron
        |
        v
Apify API Collector
  - Yad2 Actor
  - Madlan Actor
        |
        v
Normalize listings
        |
        v
Filter Agent
        |
        v
Deal Scoring Agent
        |
        v
SQLite history
        |
        v
Email Report Agent
```

## Quick start

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env`:

```env
APIFY_TOKEN=your_apify_token_here
EMAIL_BACKEND=console
EMAIL_TO=you@example.com
EMAIL_FROM=you@example.com
APIFY_BUDGET_GUARD_ENABLED=true
APIFY_MONTHLY_BUDGET_USD=5.00
APIFY_BUDGET_SAFETY_BUFFER_USD=0.10
APIFY_SET_PLATFORM_HARD_LIMIT=true
APIFY_BUDGET_FAIL_CLOSED=true
```

Run one profile first:

```bash
python -m app.main --config configs/searches.yaml --profile givatayim_4_rooms_deals --send-email --include-existing
```

Run all enabled profiles:

```bash
python -m app.main --config configs/searches.yaml --all-profiles --send-email
```

The console email backend writes the generated report to `artifacts/latest_report.html`.

## Real API connection

The project uses the official `apify-client` Python package and calls configured Actors with your `APIFY_TOKEN`.

The Actor IDs and Actor inputs are stored in `configs/searches.yaml`, not hard-coded in Python. This is important because third-party Actor input schemas can change. If an Actor changes its fields, update only the YAML `run_input` section.

Example source configuration:

```yaml
sources:
  - name: yad2
    actor_id: swerve/yad2-scraper
    limit: 5
    estimated_cost_usd: 0.05
    run_input:
      city: "גבעתיים"
      dealType: sale
      propertyType: apartment
      roomsMin: 4
      roomsMax: 4
      maxPrice: 3300000
      maxItems: 5
```

## Search profiles included

### Givatayim 4-room bargain apartments

```yaml
name: givatayim_4_rooms_deals
city: גבעתיים
rooms: 4
max_price: 3300000
min_size_sqm: 80
```

### Haifa 3-room good-area investment apartments

This profile searches sale listings in good Haifa neighborhoods and prefers listings that mention the apartment is rented.

```yaml
name: haifa_3_rooms_rented_good_area
city: חיפה
rooms: 3
max_price: 1450000
min_size_sqm: 55
required_any_keywords:
  - מושכרת
  - מושכר
  - שוכר
  - שכירות
```

Change neighborhoods, max price, target price per square meter, and keywords in `configs/searches.yaml`.

## Email backends

### Console backend

Good for testing. Does not send a real email.

```env
EMAIL_BACKEND=console
```

### SMTP backend

Good with Gmail App Password, SendGrid SMTP, Mailgun SMTP, or any standard SMTP server.

```env
EMAIL_BACKEND=smtp
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password
EMAIL_FROM=your_email@gmail.com
EMAIL_TO=your_email@gmail.com
```

### Gmail API backend

Use this only after you create OAuth credentials and store a valid user token JSON.

```env
EMAIL_BACKEND=gmail_api
GMAIL_TOKEN_JSON={...full token json...}
EMAIL_FROM=your_email@gmail.com
EMAIL_TO=your_email@gmail.com
```

## GitHub Actions

The included workflow runs daily and can also be triggered manually.

Required GitHub Secrets:

```text
APIFY_TOKEN
EMAIL_BACKEND
EMAIL_FROM
EMAIL_TO
SMTP_HOST
SMTP_PORT
SMTP_USERNAME
SMTP_PASSWORD
```

Budget guard values are set directly in the workflow to safe defaults:

```text
APIFY_BUDGET_GUARD_ENABLED=true
APIFY_MONTHLY_BUDGET_USD=5.00
APIFY_BUDGET_SAFETY_BUFFER_USD=0.10
APIFY_SET_PLATFORM_HARD_LIMIT=true
APIFY_BUDGET_FAIL_CLOSED=true
```

## Cost control and $5 budget guard

The project includes two cost controls:

1. Apify platform hard limit.
2. Local Python budget guard before each Actor run.

Behavior:

- Before running each Apify Actor, the agent calls the Apify monthly usage endpoint.
- If current monthly usage is already close to the configured budget, the run is skipped.
- The report still gets generated and includes a system note explaining that the budget guard blocked collection.
- If `--send-email` is enabled, the budget warning is included in the email report.
- When `APIFY_SET_PLATFORM_HARD_LIMIT=true`, the agent also attempts to set Apify's own monthly platform hard limit to the configured budget.

Use small limits while testing:

```yaml
limit: 5
estimated_cost_usd: 0.05
run_input:
  maxItems: 5
```

`estimated_cost_usd` is only a conservative pre-run estimate used by the local budget guard. The real Apify charge is determined by the Actor pricing and Apify platform usage.

## Notes

- This is not financial or real-estate investment advice.
- Always verify listing availability, legal status, building condition, elevator, parking, shelter room, taxes, and brokerage fees with the seller or agent.
- Some listing fields differ between sources. The normalizer is defensive and supports many common field names.
- If an Actor schema changes, update `configs/searches.yaml` rather than changing Python code.
