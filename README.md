# Rocket Brands Prospect Scraper

Modular prospect discovery & enrichment for Rocket Brands Media. Finds potential media-buying clients across iGaming, sports betting, crypto, mobile games, apps, prediction markets, esports, and fantasy sports — then enriches with emails, decision-makers, socials, and affiliate-program signals.

## Quick start

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Optional: browsers for Scrapling's stealth fetcher
playwright install chromium

cp .env.example .env
# Edit .env — SERPER_API_KEY and PROXYCURL_API_KEY are strongly recommended
```

The scraper works with ZERO API keys (raw scraping mode) but is more reliable and higher volume with keys set.

## CLI

```bash
# Discover across all verticals
python cli.py discover --vertical all --pages 2

# Discover a single vertical
python cli.py discover --vertical casino --pages 3

# Run just one source with a direct query
python cli.py discover --source google_play --query "casino slots" --vertical casino
python cli.py discover --source google_maps --query "online casino company" --vertical casino

# Scrape a directory page (learn-by-example via AutoScraper)
python cli.py scrape-directory \
  --url "https://www.askgamblers.com/online-casinos/all" \
  --example "Stake Casino" \
  --vertical casino

# Enrich an existing CSV (deep website crawl)
python cli.py enrich --input data/prospects.csv --deep

# Enrich with LinkedIn (requires PROXYCURL_API_KEY)
python cli.py enrich --input data/prospects.csv --linkedin

# Stats + export
python cli.py stats --input data/prospects.csv
python cli.py export --input data/prospects.csv --output hot_leads.csv --min-score 70
```

## Architecture

```
config/          settings, verticals, blacklists
sources/         google_search, google_maps, google_play, directories, linkedin, website
enrichment/      email_finder, contact_finder, social_finder, affiliate_detector, ai_extractor
core/            models (Pydantic), deduplication, storage (CSV/SQLite), rate_limiter, proxy, browser
pipeline.py      discover + enrich + score orchestration
cli.py           Typer + Rich CLI
tests/           pytest unit tests
```

## Data flow

1. **Discovery** — queries each source (Google Search, Google Maps, Google Play) for every query defined in `config/verticals.py`. Returns raw `Prospect` objects.
2. **Dedup** — domain-level + normalized company-name deduplication against the existing CSV. Cross-source matches are merged (richest record wins).
3. **Enrichment** — for each new prospect, `sources/website.py` deep-crawls `/contact`, `/about`, `/team`, `/partners`, `/affiliates`, etc. Extracts:
   - Emails (regex + blacklist filter, prioritized by `partner|affiliate|marketing|media|...` prefixes)
   - Social links (LinkedIn, Twitter/X, IG, Telegram, Discord, Facebook, YouTube, TikTok)
   - Phone numbers
   - Decision-maker names + titles (filtered to the `TARGET_TITLES` list)
   - Affiliate/partner program signals
4. **LinkedIn** (optional) — `sources/linkedin.py` uses Proxycurl API for company + filtered-employees lookup.
5. **Scoring** — 0–100 lead quality score based on email presence, partnership-friendly prefixes, affiliate program, decision-maker contacts, socials, Play Store signals, etc.
6. **Storage** — append to CSV (flat columns for spreadsheet use), with optional SQLite support in `core/storage.py`.

## Rate limiting

Per-domain delays, configured in `config/settings.py::RATE_LIMITS`:
- `google.com`: 3–8s
- `google.com/maps`: 5–10s
- `linkedin.com`: 5–15s
- `play.google.com`: 1–3s
- default: 1–4s

## Tech notes

- **Scrapling** for all HTML fetching (Fetcher + StealthyFetcher) with anti-bot bypass. `core/browser.py` falls back to `httpx` if Scrapling is unavailable.
- **httpx** (async-capable) for API calls (Serper, Proxycurl).
- **Pydantic v2** everywhere — no raw dicts.
- **Polars** can be plugged in for analytics on large CSVs.
- **loguru** for all logging (`logs/scraper_*.log`, 10 MB rotation, 7 day retention).
- **tenacity** available for retry decorators on HTTP calls.

## Deployment on DigitalOcean

```bash
git clone <repo> rocket-scraper && cd rocket-scraper
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env && nano .env

tmux new -s scraper
python cli.py discover --vertical all --pages 2
# Ctrl+B, D to detach

# Cron: daily discovery
# 0 6 * * * cd ~/rocket-scraper && source venv/bin/activate && python cli.py discover --vertical all --pages 1 >> logs/cron.log 2>&1
```

Memory tips for the 2GB droplet: batch size 50 (default), save incrementally after each batch, StealthyFetcher in headless mode only.

## Google Maps scraping at scale

For volume, prefer the `gosom/google-maps-scraper` Docker image over the built-in Python scraper:

```bash
docker pull gosom/google-maps-scraper
printf "online casino company\nsports betting company\ngame studio\n" > queries.txt
docker run -v $PWD/queries.txt:/queries -v $PWD/results:/results \
  gosom/google-maps-scraper -input /queries -results /results/output.csv -email -depth 1 -exit-on-inactivity 3m
```

Then ingest the CSV via a quick Python script that maps columns into the `Prospect` model.

## Tests

```bash
pytest -q
```

## Success criteria

After a full run across all verticals:

- 1,000–3,000 new prospects discovered
- 40–60% with at least one email
- 15–25% with a decision-maker contact
- 20–30% with an affiliate/partner program detected
- 70%+ with a LinkedIn company page
- Clean CSV ready for outreach, scored and sorted by lead quality (score ≥ 70 = hot)
