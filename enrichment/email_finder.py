"""Email extraction and validation helpers."""
from __future__ import annotations

import re

from config.blacklists import EMAIL_BLACKLIST_SUBSTRINGS, PREFERRED_EMAIL_PREFIXES

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


def is_valid_email(email: str) -> bool:
    e = (email or "").lower().strip()
    if not e or "@" not in e:
        return False
    if len(e) > 100:
        return False
    for bad in EMAIL_BLACKLIST_SUBSTRINGS:
        if bad in e:
            return False
    local, _, domain = e.partition("@")
    if not local or not domain or "." not in domain:
        return False
    return True


def extract_emails(html_or_text: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for m in EMAIL_RE.findall(html_or_text or ""):
        e = m.strip().lower()
        if is_valid_email(e) and e not in seen:
            seen.add(e)
            out.append(e)
    return out


def pick_primary(emails: list[str]) -> str:
    if not emails:
        return ""
    for prefix in PREFERRED_EMAIL_PREFIXES:
        for e in emails:
            if e.split("@")[0].startswith(prefix):
                return e
    return emails[0]
