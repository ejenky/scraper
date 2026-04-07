"""Outreach system configuration — loaded from environment."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

OUTREACH_DB = DATA_DIR / "outreach.db"
PROSPECTS_CSV = DATA_DIR / "prospects.csv"

# --- API keys ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# --- Tracking ---
TRACKING_DOMAIN = os.getenv("TRACKING_DOMAIN", "localhost")
TRACKING_PORT = int(os.getenv("TRACKING_PORT", "8502"))
TRACKING_BASE_URL = f"http://{TRACKING_DOMAIN}:{TRACKING_PORT}"

# --- Sending limits (hard-capped) ---
_ABS_MAX_PER_DAY = 30  # never exceed this, regardless of env
MAX_EMAILS_PER_DAY_PER_ACCOUNT = min(
    int(os.getenv("MAX_EMAILS_PER_DAY_PER_ACCOUNT", "25")), _ABS_MAX_PER_DAY
)
MAX_EMAILS_PER_HOUR_PER_ACCOUNT = int(os.getenv("MAX_EMAILS_PER_HOUR_PER_ACCOUNT", "8"))
MIN_DELAY_BETWEEN_EMAILS = int(os.getenv("MIN_DELAY_BETWEEN_EMAILS", "120"))
MAX_DELAY_BETWEEN_EMAILS = int(os.getenv("MAX_DELAY_BETWEEN_EMAILS", "300"))

# --- Business hours (recipient-agnostic — uses server/user tz) ---
BUSINESS_HOUR_START = 8   # 8am
BUSINESS_HOUR_END = 18    # 6pm
BUSINESS_DAYS = {0, 1, 2, 3, 4}  # Mon-Fri

# --- Follow-up schedule ---
FOLLOWUP_DAYS = {
    "followup_1": 3,
    "followup_2": 7,
    "followup_3": 14,
}

# --- Gmail SMTP ---
GMAIL_SMTP_HOST = "smtp.gmail.com"
GMAIL_SMTP_PORT = 587  # TLS (NOT 465/SSL)


@dataclass
class GmailAccount:
    email: str
    password: str
    display_name: str

    def configured(self) -> bool:
        return bool(self.email and self.password)


def load_gmail_accounts() -> list[GmailAccount]:
    """Load up to 2 Gmail accounts from env. Returns only configured ones."""
    accounts: list[GmailAccount] = []
    for i in (1, 2):
        email = os.getenv(f"GMAIL_USER_{i}", "").strip()
        password = os.getenv(f"GMAIL_APP_PASSWORD_{i}", "").strip()
        display = os.getenv(f"GMAIL_DISPLAY_NAME_{i}", f"Rocket Brands {i}").strip()
        if email and password:
            accounts.append(GmailAccount(email=email, password=password, display_name=display))
    return accounts


def has_groq() -> bool:
    return bool(GROQ_API_KEY)
