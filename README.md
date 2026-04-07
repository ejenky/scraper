# 🚀 Rocket Brands Scraper + Outreach

End-to-end prospect discovery, enrichment, and AI-powered cold outreach for Rocket Brands Media.

**Scraper:** finds potential media-buying clients across iGaming, sports betting, crypto, mobile games, apps, prediction markets, esports, and fantasy sports — then enriches with emails, decision-makers, socials, and affiliate-program signals.

**Outreach:** generates personalized cold emails via Groq LLM (free tier), sends from rotating Gmail accounts with hard-capped rate limiting, tracks opens/clicks, and automates 3/7/14-day follow-up sequences.

Both components ship with Streamlit dashboards.

## Quick Start

```bash
git clone https://github.com/ejenky/scraper.git
cd scraper
bash deploy.sh
```

This installs Python deps, Playwright browsers, creates a `.env` template, and opens port 8501 for the dashboard.

## Usage

### Scraper CLI

```bash
source venv/bin/activate

# Discover prospects across all verticals
python cli.py discover --vertical all --pages 2

# Single vertical
python cli.py discover --vertical casino --pages 3

# Single source + direct query
python cli.py discover --source google_play --query "casino slots" --vertical casino
python cli.py discover --source google_maps --query "online casino company" --vertical casino

# Scrape a directory page (AutoScraper learn-by-example)
python cli.py scrape-directory \
    --url "https://www.askgamblers.com/online-casinos/all" \
    --example "Stake Casino" --vertical casino

# Enrich existing CSV with deep website crawl
python cli.py enrich --input data/prospects.csv --deep

# Enrich with LinkedIn (requires PROXYCURL_API_KEY)
python cli.py enrich --input data/prospects.csv --linkedin

# Stats and export
python cli.py stats --input data/prospects.csv
python cli.py export --input data/prospects.csv --output hot_leads.csv --min-score 70
```

### Convenience scripts

```bash
./run_scraper.sh      # Discover all verticals
./run_dashboard.sh    # Start scraper Streamlit dashboard
./run_outreach.sh     # Start tracking server + outreach dashboard
```

## Outreach System

AI-generated cold email with rotating Gmail sending, open/click tracking, and automated follow-ups. Reads prospects from `data/prospects.csv` (scraper output).

### Generate → preview → send → follow-up

```bash
source venv/bin/activate

# 1. Generate AI-personalized drafts (uses Groq free tier)
python outreach_cli.py generate --campaign "Casino Q2" --vertical casino --min-score 20

# 2. Preview a few before sending
python outreach_cli.py preview --campaign "Casino Q2" --limit 5

# 3. Dry run
python outreach_cli.py send --campaign "Casino Q2" --dry-run

# 4. Send for real (respects rate limits + business hours)
python outreach_cli.py send --campaign "Casino Q2"

# 5. Campaign status
python outreach_cli.py status --campaign "Casino Q2"

# 6. Gmail account health
python outreach_cli.py health

# 7. Generate and send due follow-ups (3/7/14 days after initial)
python outreach_cli.py followup --campaign "Casino Q2" --auto-send

# 8. Manual reply tracking
python outreach_cli.py reply prospect@example.com

# 9. Unsubscribe
python outreach_cli.py unsubscribe prospect@example.com

# 10. Export campaign results
python outreach_cli.py export --campaign "Casino Q2" --output results.csv
```

### Tracking server (port 8502)

Serves the 1×1 tracking pixel and click-redirect endpoints. Must be running for open/click tracking to work.

```bash
uvicorn tracking_server:app --host 0.0.0.0 --port 8502
# or
python outreach_cli.py track-server
```

### Outreach dashboard (port 8503)

```bash
streamlit run outreach_dashboard.py --server.port 8503 --server.address 0.0.0.0
```

Shows: campaign metrics, open/click/reply rates, timeline chart, per-vertical performance, per-account usage, filtered email table, due-for-followup list, recent opens.

### Deliverability rules (hard-coded)

1. Max **25** emails/day per Gmail account (hard-capped at 30 regardless of env setting)
2. Max **8** emails/hour per account
3. Random **2–5 minute** delay between sends (never consistent intervals)
4. **Business hours only**: 8am–6pm Mon–Fri
5. **Plain text always included** (REQUIRED for deliverability)
6. **No tracking pixel on initial email** — only added on follow-ups
7. **No images, no attachments, no links** in initial emails
8. **Subject line validation** — rejects ALL CAPS, `!`/`?`, emojis, >10 words
9. **Unsubscribe check** before every send; `/u/<id>` endpoint for self-serve
10. **Bounce check** before every send; heuristic detection on SMTP errors
11. **Follow-ups threaded** — `Re:` subject + `In-Reply-To`/`References` headers
12. **Word limit** on body: trimmed if >160 words

### Gmail setup

1. Enable 2-Step Verification on the Google account
2. Go to https://myaccount.google.com/apppasswords
3. Generate an App Password (Mail → Other)
4. Put the 16-character password in `GMAIL_APP_PASSWORD_1` (never the regular password)
5. Repeat for the second account if you have one

The system works with 1 or 2 accounts. Two accounts doubles your daily send capacity (50 emails/day total).

### Long-running jobs

```bash
tmux new -s scraper
python cli.py discover --vertical all --pages 3
# Ctrl+B, D to detach
tmux attach -t scraper
```

## Dashboard

Launch the Streamlit dashboard to visualize, filter, and export prospects:

```bash
./run_dashboard.sh
# OR
streamlit run dashboard.py --server.port 8501 --server.address 0.0.0.0
```

Then open `http://<droplet-ip>:8501`.

Features:
- 6-metric summary (total, with email, with contacts, affiliate programs, avg score, hot leads)
- Filter by vertical, source, min score, email-only
- Sortable full data table (500px)
- Charts: vertical / source / score distribution
- Top 20 hot leads with color-coded scoring (🟢 70+ / 🟡 40–69 / 🔴 0–39)
- Download filtered CSV
- Auto-refresh every 30 seconds (sidebar toggle)
- Cached Polars-based data loading (ttl=30, invalidated on CSV mtime)

The dashboard reads from `data/prospects.csv` (the same path the scraper writes to). It also falls back to `prospects.csv` in the project root if present. If no CSV exists yet it shows a "run scraper first" message rather than crashing.

## API Keys

All keys are **optional** — the scraper runs in pure raw-scraping mode with none set, and progressively unlocks more capability as keys are added.

| Key | What it does | Required? | Cost |
| --- | --- | --- | --- |
| `SERPER_API_KEY` | Google SERP via Serper.dev (clean JSON, no blocking) | Strongly recommended | ~$50/mo for 5k searches |
| `PROXYCURL_API_KEY` | LinkedIn company + employee enrichment | Optional | ~$0.01/profile |
| `LINKEDIN_COOKIE` | Cookie-based LinkedIn scraping fallback | Optional | Free |
| `SCRAPER_API_KEY` | ScraperAPI residential proxy rotation | Optional | Pay-as-you-go |
| `BRIGHTDATA_USERNAME/PASSWORD` | BrightData proxy rotation | Optional | Pay-as-you-go |
| `OPENAI_API_KEY` | ScrapeGraphAI LLM extraction fallback | Optional | Pay-as-you-go |
| `GROQ_API_KEY` | Llama 3.1 70B for email generation | Strongly recommended (outreach) | **Free** tier: 14k req/day |
| `GMAIL_USER_1` / `GMAIL_APP_PASSWORD_1` | Sending Gmail account 1 | Required (outreach) | Free |
| `GMAIL_USER_2` / `GMAIL_APP_PASSWORD_2` | Sending Gmail account 2 | Optional — doubles capacity | Free |

Without any keys: Google Search uses raw scraping via Scrapling StealthyFetcher (slower, lower volume). Maps and Play Store work out of the box.

## Architecture

```
scraper/
├── config/
│   ├── settings.py          # API keys, rate limits, paths
│   ├── verticals.py         # 8 verticals × queries × target titles
│   └── blacklists.py        # Domain/email/affiliate lists
├── sources/
│   ├── google_search.py     # Serper API + raw scraping fallback
│   ├── google_maps.py       # Maps business discovery
│   ├── google_play.py       # Play Store publisher discovery
│   ├── directories.py       # AutoScraper-based directory scraping
│   ├── linkedin.py          # Proxycurl enrichment
│   └── website.py           # Deep crawler (emails, socials, contacts, affiliates)
├── enrichment/
│   ├── email_finder.py      # Regex + blacklist + prefix priority
│   ├── contact_finder.py    # Decision-maker name + title extraction
│   ├── social_finder.py     # 8 social platforms
│   ├── affiliate_detector.py
│   └── ai_extractor.py      # AutoScraper learn-by-example
├── core/
│   ├── models.py            # Pydantic v2 Prospect, ContactPerson, SocialLinks
│   ├── deduplication.py     # Domain + normalized-name merge
│   ├── storage.py           # CSV (flat) + SQLite
│   ├── rate_limiter.py      # Per-domain jittered delays
│   ├── proxy.py             # ScraperAPI / BrightData / file-based rotation
│   └── browser.py           # Scrapling wrapper + httpx fallback
├── pipeline.py              # Discover → dedup → enrich → score → save
├── cli.py                   # Scraper CLI (Typer + Rich)
├── dashboard.py             # Scraper Streamlit dashboard (port 8501)
├── outreach/
│   ├── models.py            # EmailRecord, Campaign, SequenceStep, EmailStatus
│   ├── config.py            # Env loading, Gmail accounts, rate limits
│   ├── storage.py           # SQLite (campaigns, emails, tracking, unsub, bounces)
│   ├── templates.py         # System prompt, spintax, validators
│   ├── generator.py         # Groq LLM email generation + template fallback
│   ├── sender.py            # Gmail SMTP with rotation + rate limiting
│   ├── scheduler.py         # 3/7/14-day follow-up automation
│   └── warmth.py            # Account health checks
├── outreach_cli.py          # Outreach CLI
├── outreach_dashboard.py    # Outreach Streamlit dashboard (port 8503)
├── tracking_server.py       # FastAPI tracking pixel + click redirect (port 8502)
├── deploy.sh                # One-shot droplet deployment
├── run_scraper.sh           # Convenience runner
├── run_dashboard.sh         # Scraper dashboard runner
├── run_outreach.sh          # Tracking + outreach dashboard runner
└── tests/                   # pytest unit tests
```

## Data Flow

1. **Discovery** — queries each source (Google Search, Maps, Play) for every query in `config/verticals.py`.
2. **Dedup** — domain-level + normalized company-name dedup against existing CSV. Cross-source matches merged.
3. **Enrichment** — deep crawl of `/contact`, `/about`, `/team`, `/partners`, `/affiliates`, etc. Extracts emails (prefix-prioritized), socials (8 platforms), phones, decision-makers (filtered to `TARGET_TITLES`), and affiliate-program signals.
4. **LinkedIn** (optional) — Proxycurl company + filtered-employees lookup.
5. **Scoring** — 0–100 based on email presence, partnership-friendly prefixes, affiliate program, decision-maker contacts, socials, Play Store installs, Maps reviews.
6. **Storage** — append to `data/prospects.csv` (flat columns for spreadsheets), optional SQLite in `core/storage.py`.

## Rate Limits

Per-domain with jitter (`config/settings.py::RATE_LIMITS`):

| Domain | Delay |
| --- | --- |
| google.com | 3–8s |
| google.com/maps | 5–10s |
| linkedin.com | 5–15s |
| play.google.com | 1–3s |
| default | 1–4s |

## Tech Stack

- **Scrapling** — primary HTML fetcher with anti-bot bypass (Fetcher + StealthyFetcher)
- **httpx** — async API calls (Serper, Proxycurl) + fallback fetcher
- **Pydantic v2** — all data models
- **Polars** — dashboard data loading, memory-efficient
- **Streamlit** — dashboard UI
- **Typer + Rich** — CLI
- **loguru** — rotating logs (`logs/scraper_*.log`, 10 MB, 7 day retention)
- **tenacity** — retry decorators

## Memory (2GB droplet)

- Batch size 50 (default) — save incrementally
- StealthyFetcher headless mode only
- Polars over pandas
- No in-memory HTML retention past extraction

## Google Maps at scale

For volume, prefer `gosom/google-maps-scraper` Docker image over the built-in Python scraper:

```bash
docker pull gosom/google-maps-scraper
printf "online casino company\nsports betting company\ngame studio\n" > queries.txt
docker run -v $PWD/queries.txt:/queries -v $PWD/results:/results \
    gosom/google-maps-scraper \
    -input /queries -results /results/output.csv \
    -email -depth 1 -exit-on-inactivity 3m
```

## Tests

```bash
pytest -q
```

## Success Criteria

After a full run across all verticals:

- 1,000–3,000 new prospects discovered
- 40–60% with at least one email
- 15–25% with a decision-maker contact
- 20–30% with an affiliate/partner program detected
- 70%+ with a LinkedIn company page
- Clean CSV scored and sorted by lead quality (score ≥ 70 = hot)
