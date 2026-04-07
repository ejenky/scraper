"""Global configuration for Rocket Brands Prospect Scraper."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# --- Paths ---
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"
MODELS_DIR = PROJECT_ROOT / "models"
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)
MODELS_DIR.mkdir(exist_ok=True)

DEFAULT_CSV = DATA_DIR / "prospects.csv"
DEFAULT_DB = DATA_DIR / "prospects.db"

# --- API keys ---
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")
LINKEDIN_COOKIE = os.getenv("LINKEDIN_COOKIE", "")
PROXYCURL_API_KEY = os.getenv("PROXYCURL_API_KEY", "")
SCRAPER_API_KEY = os.getenv("SCRAPER_API_KEY", "")
BRIGHTDATA_USERNAME = os.getenv("BRIGHTDATA_USERNAME", "")
BRIGHTDATA_PASSWORD = os.getenv("BRIGHTDATA_PASSWORD", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# --- Rate limits (per domain) ---
RATE_LIMITS = {
    "google.com": {"min_delay": 3, "max_delay": 8},
    "google.com/maps": {"min_delay": 5, "max_delay": 10},
    "linkedin.com": {"min_delay": 5, "max_delay": 15},
    "play.google.com": {"min_delay": 1, "max_delay": 3},
    "default": {"min_delay": 1, "max_delay": 4},
}

# --- HTTP ---
DEFAULT_TIMEOUT = 20
MAX_RETRIES = 3
BATCH_SIZE = 50

# --- Scraping ---
MAX_EMAILS_PER_PROSPECT = 10
MAX_CONTACTS_PER_PROSPECT = 5
MAX_DESCRIPTION_CHARS = 300


def has_serper() -> bool:
    return bool(SERPER_API_KEY)


def has_proxycurl() -> bool:
    return bool(PROXYCURL_API_KEY)
