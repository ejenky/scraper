"""Social media profile extraction."""
from __future__ import annotations

import re

from core.models import SocialLinks

PATTERNS = {
    "linkedin":  re.compile(r"https?://(?:www\.)?linkedin\.com/(?:company|in)/[\w\-]+"),
    "twitter":   re.compile(r"https?://(?:www\.)?(?:twitter|x)\.com/[\w_]+"),
    "instagram": re.compile(r"https?://(?:www\.)?instagram\.com/[\w.]+"),
    "telegram":  re.compile(r"https?://(?:www\.)?t\.me/[\w_]+"),
    "discord":   re.compile(r"https?://(?:www\.)?discord\.(?:gg|com)/[\w]+"),
    "facebook":  re.compile(r"https?://(?:www\.)?facebook\.com/[\w.\-]+"),
    "youtube":   re.compile(r"https?://(?:www\.)?youtube\.com/(?:@[\w\-.]+|channel/[\w\-]+|c/[\w\-]+|user/[\w\-]+)"),
    "tiktok":    re.compile(r"https?://(?:www\.)?tiktok\.com/@[\w.\-]+"),
}


def extract_socials(html: str) -> SocialLinks:
    found: dict[str, str] = {}
    for key, pat in PATTERNS.items():
        m = pat.search(html or "")
        if m:
            found[key] = m.group(0)
    return SocialLinks(**found)
