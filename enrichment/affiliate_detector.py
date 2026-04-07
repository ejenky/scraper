"""Affiliate / partner program detection."""
from __future__ import annotations

from config.blacklists import AFFILIATE_INDICATORS


def has_affiliate_program(text: str) -> bool:
    t = (text or "").lower()
    return any(kw in t for kw in AFFILIATE_INDICATORS)


def find_affiliate_url(links: list[str]) -> str:
    keywords = ("affiliate", "partner", "referral", "ambassador")
    for link in links:
        low = link.lower()
        if any(kw in low for kw in keywords):
            return link
    return ""
