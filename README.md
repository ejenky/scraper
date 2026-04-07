# 🚀 Rocket Brands Prospect Scraper

Modular prospect discovery & enrichment for Rocket Brands Media. Finds potential media-buying clients across **iGaming, sports betting, crypto, mobile games, apps, prediction markets, esports, and fantasy sports** — then enriches with emails, decision-makers, socials, and affiliate-program signals. Ships with a Streamlit dashboard.

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
./run_dashboard.sh    # Start Streamlit dashboard
```

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
├── cli.py                   # Typer + Rich CLI
├── dashboard.py             # Streamlit dashboard
├── deploy.sh                # One-shot droplet deployment
├── run_scraper.sh           # Convenience runner
├── run_dashboard.sh         # Convenience runner
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
