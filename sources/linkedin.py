"""LinkedIn enrichment. Tiered: Proxycurl API > cookie scraper > Google dorking."""
from __future__ import annotations

from typing import Optional

import httpx
from loguru import logger

from config.settings import DEFAULT_TIMEOUT, PROXYCURL_API_KEY, has_proxycurl
from config.verticals import TARGET_TITLES
from core.models import ContactPerson, Prospect


def enrich_company_proxycurl(linkedin_url: str) -> dict:
    """Fetch company profile from Proxycurl."""
    if not has_proxycurl():
        return {}
    try:
        resp = httpx.get(
            "https://nubela.co/proxycurl/api/linkedin/company",
            params={"url": linkedin_url},
            headers={"Authorization": f"Bearer {PROXYCURL_API_KEY}"},
            timeout=DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning(f"Proxycurl company error for {linkedin_url}: {e}")
        return {}


def search_employees_proxycurl(linkedin_url: str, titles: Optional[list[str]] = None) -> list[dict]:
    if not has_proxycurl():
        return []
    titles = titles or TARGET_TITLES
    try:
        resp = httpx.get(
            "https://nubela.co/proxycurl/api/linkedin/company/employees/",
            params={
                "url": linkedin_url,
                "role_search": "|".join(titles[:5]),
                "page_size": "10",
            },
            headers={"Authorization": f"Bearer {PROXYCURL_API_KEY}"},
            timeout=DEFAULT_TIMEOUT * 2,
        )
        resp.raise_for_status()
        return resp.json().get("employees", []) or []
    except Exception as e:
        logger.warning(f"Proxycurl employees error for {linkedin_url}: {e}")
        return []


def enrich(prospect: Prospect) -> Prospect:
    """Enrich a prospect using LinkedIn (if configured)."""
    if not prospect.socials.linkedin:
        return prospect

    if has_proxycurl():
        company = enrich_company_proxycurl(prospect.socials.linkedin)
        if company:
            if not prospect.description and company.get("description"):
                prospect.description = company["description"][:300]
            if not prospect.company_size:
                size = company.get("company_size_on_linkedin") or company.get("company_size")
                if isinstance(size, (list, tuple)) and len(size) == 2:
                    prospect.company_size = f"{size[0]}-{size[1]}"
                elif size:
                    prospect.company_size = str(size)
        employees = search_employees_proxycurl(prospect.socials.linkedin)
        for emp in employees[:5]:
            profile = emp.get("profile", {}) or {}
            name = (profile.get("full_name") or "").strip()
            title = (profile.get("occupation") or profile.get("headline") or "").strip()
            url = emp.get("profile_url", "") or profile.get("public_identifier", "")
            if not name:
                continue
            if not any(t in title.lower() for t in TARGET_TITLES):
                continue
            prospect.contacts.append(
                ContactPerson(name=name, title=title, linkedin_url=url)
            )
    else:
        logger.debug("LinkedIn enrichment skipped: no PROXYCURL_API_KEY")

    return prospect
