"""Deep website crawler — extract emails, socials, contacts, affiliate signals."""
from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urljoin, urlparse

from loguru import logger

from config.blacklists import (
    AFFILIATE_INDICATORS,
    EMAIL_BLACKLIST_SUBSTRINGS,
    PREFERRED_EMAIL_PREFIXES,
)
from config.settings import MAX_CONTACTS_PER_PROSPECT, MAX_EMAILS_PER_PROSPECT
from config.verticals import TARGET_TITLES
from core.browser import fetch
from core.models import ContactPerson, Prospect, SocialLinks

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

SOCIAL_PATTERNS = {
    "linkedin":  re.compile(r"https?://(?:www\.)?linkedin\.com/(?:company|in)/[\w\-]+"),
    "twitter":   re.compile(r"https?://(?:www\.)?(?:twitter|x)\.com/[\w_]+"),
    "instagram": re.compile(r"https?://(?:www\.)?instagram\.com/[\w.]+"),
    "telegram":  re.compile(r"https?://(?:www\.)?t\.me/[\w_]+"),
    "discord":   re.compile(r"https?://(?:www\.)?discord\.(?:gg|com)/[\w]+"),
    "facebook":  re.compile(r"https?://(?:www\.)?facebook\.com/[\w.\-]+"),
    "youtube":   re.compile(r"https?://(?:www\.)?youtube\.com/(?:@[\w\-.]+|channel/[\w\-]+|c/[\w\-]+|user/[\w\-]+)"),
    "tiktok":    re.compile(r"https?://(?:www\.)?tiktok\.com/@[\w.\-]+"),
}

PHONE_RE = re.compile(r"\+?\d[\d\s\-().]{7,}\d")

CONTACT_PATHS = [
    "/contact", "/contact-us",
    "/about", "/about-us",
    "/team", "/our-team", "/leadership", "/management",
    "/partners", "/partnership", "/become-a-partner", "/partner-with-us",
    "/affiliates", "/affiliate-program", "/affiliate", "/referral",
    "/advertise", "/advertise-with-us", "/advertising", "/media-buying",
    "/media", "/media-kit", "/press",
    "/careers", "/jobs",
]


def _valid_email(email: str) -> bool:
    e = email.lower().strip()
    if not e or "@" not in e:
        return False
    for bad in EMAIL_BLACKLIST_SUBSTRINGS:
        if bad in e:
            return False
    if len(e) > 100:
        return False
    return True


def extract_emails(html: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for m in EMAIL_RE.findall(html or ""):
        e = m.strip().lower()
        # unescape common HTML entities
        e = e.replace("%40", "@").replace(" ", "")
        if _valid_email(e) and e not in seen:
            seen.add(e)
            found.append(e)
    return found


def pick_primary_email(emails: list[str]) -> str:
    if not emails:
        return ""
    for prefix in PREFERRED_EMAIL_PREFIXES:
        for e in emails:
            local = e.split("@")[0]
            if local.startswith(prefix):
                return e
    return emails[0]


def extract_socials(html: str) -> SocialLinks:
    found: dict[str, str] = {}
    for key, pat in SOCIAL_PATTERNS.items():
        m = pat.search(html or "")
        if m:
            found[key] = m.group(0)
    return SocialLinks(**found)


def extract_phone(text: str) -> str:
    m = PHONE_RE.search(text or "")
    if not m:
        return ""
    phone = re.sub(r"[^\d+]", "", m.group(0))
    if len(phone) < 8 or len(phone) > 16:
        return ""
    return m.group(0).strip()


def detect_affiliate(text_lower: str) -> bool:
    return any(kw in text_lower for kw in AFFILIATE_INDICATORS)


def extract_contacts_from_text(text: str) -> list[ContactPerson]:
    """Fallback regex-based contact extraction: 'Name - Title' patterns."""
    contacts: list[ContactPerson] = []
    seen: set[str] = set()
    pattern = re.compile(
        r"([A-Z][a-z]+(?:\s[A-Z][a-z]+){1,3})\s*[-–—,]\s*([A-Z][\w\s&/]{3,60})"
    )
    for m in pattern.finditer(text or ""):
        name = m.group(1).strip()
        title = m.group(2).strip()
        if name in seen:
            continue
        title_lower = title.lower()
        if not any(t in title_lower for t in TARGET_TITLES):
            continue
        seen.add(name)
        contacts.append(ContactPerson(name=name, title=title))
        if len(contacts) >= MAX_CONTACTS_PER_PROSPECT:
            break
    return contacts


def _base_url(url: str) -> Optional[str]:
    try:
        p = urlparse(url if "://" in url else "http://" + url)
        if not p.netloc:
            return None
        return f"{p.scheme or 'https'}://{p.netloc}"
    except Exception:
        return None


def crawl_website(url: str, deep: bool = True, max_pages: int = 8) -> dict:
    """Crawl a website and return extracted data."""
    base = _base_url(url)
    if not base:
        return {}

    pages_to_fetch = [base]
    if deep:
        pages_to_fetch.extend(urljoin(base, p) for p in CONTACT_PATHS)
        pages_to_fetch = pages_to_fetch[: max_pages + 1]

    all_html: list[str] = []
    all_text: list[str] = []
    affiliate_url = ""

    for page_url in pages_to_fetch:
        try:
            page = fetch(page_url)
        except Exception as e:
            logger.debug(f"fetch error {page_url}: {e}")
            continue
        if page is None:
            continue
        html = getattr(page, "html_content", "") or getattr(page, "body", "") or ""
        if not html:
            continue
        all_html.append(html)
        try:
            text = page.text if hasattr(page, "text") else ""
        except Exception:
            text = ""
        if not text:
            text = re.sub(r"<[^>]+>", " ", html)
        all_text.append(text)
        path_lower = page_url.lower()
        if (not affiliate_url) and any(k in path_lower for k in ("affiliate", "partner", "referral")):
            affiliate_url = page_url

    if not all_html:
        return {}

    merged_html = "\n".join(all_html)
    merged_text = "\n".join(all_text)
    text_lower = merged_text.lower()

    emails = extract_emails(merged_html)[:MAX_EMAILS_PER_PROSPECT]
    socials = extract_socials(merged_html)
    phone = extract_phone(merged_text)
    has_aff = detect_affiliate(text_lower)
    contacts = extract_contacts_from_text(merged_text)

    return {
        "emails": emails,
        "primary_email": pick_primary_email(emails),
        "socials": socials,
        "phone": phone,
        "has_affiliate_program": has_aff,
        "affiliate_url": affiliate_url if has_aff else "",
        "contacts": contacts,
    }


def enrich_prospect(prospect: Prospect, deep: bool = True) -> Prospect:
    """Run deep crawl on a prospect and populate missing fields."""
    url = prospect.website or (f"https://{prospect.domain}" if prospect.domain else "")
    if not url:
        return prospect
    data = crawl_website(url, deep=deep)
    if not data:
        return prospect

    # Merge fields without clobbering existing data
    if data.get("emails"):
        merged = list(prospect.all_emails)
        for e in data["emails"]:
            if e not in merged:
                merged.append(e)
        prospect.all_emails = merged[:MAX_EMAILS_PER_PROSPECT]
    if not prospect.primary_email and data.get("primary_email"):
        prospect.primary_email = data["primary_email"]
    if not prospect.phone and data.get("phone"):
        prospect.phone = data["phone"]
    if data.get("has_affiliate_program"):
        prospect.has_affiliate_program = True
        if data.get("affiliate_url") and not prospect.affiliate_url:
            prospect.affiliate_url = data["affiliate_url"]
    socials = data.get("socials")
    if socials:
        cur = prospect.socials.model_dump()
        new = socials.model_dump()
        for k, v in new.items():
            if v and not cur.get(k):
                cur[k] = v
        prospect.socials = SocialLinks(**cur)
    if data.get("contacts") and not prospect.contacts:
        prospect.contacts = data["contacts"][:MAX_CONTACTS_PER_PROSPECT]
    return prospect
