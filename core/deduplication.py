"""Deduplication helpers."""
from __future__ import annotations

import re
from urllib.parse import urlparse

from core.models import Prospect


def normalize_domain(url: str) -> str:
    """Extract a clean, lowercased domain from any URL or bare domain."""
    if not url:
        return ""
    url = url.strip()
    if "://" not in url:
        url = "http://" + url
    try:
        host = urlparse(url).netloc or urlparse(url).path
    except Exception:
        host = url
    host = host.split("/")[0].split("?")[0]
    host = re.sub(r"^www\.", "", host, flags=re.IGNORECASE)
    return host.lower().strip()


_SUFFIXES = [
    " inc.",
    " inc",
    " llc",
    " ltd.",
    " ltd",
    " corp.",
    " corp",
    " limited",
    " gmbh",
    " s.a.",
    " sa",
    " ag",
    " pty",
    " co.",
    " co",
    " plc",
    " bv",
    " oy",
]


def normalize_company_name(name: str) -> str:
    """Normalize a company name for fuzzy matching."""
    if not name:
        return ""
    name = name.lower().strip()
    # strip trademark chars
    name = re.sub(r"[®™©]", "", name)
    # strip legal suffixes
    for suffix in _SUFFIXES:
        if name.endswith(suffix):
            name = name[: -len(suffix)].strip()
    # collapse whitespace and non-word chars
    name = re.sub(r"[^\w\s]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


class Deduplicator:
    """Track seen domains and company names; merge duplicates."""

    def __init__(self) -> None:
        self.by_domain: dict[str, Prospect] = {}
        self.by_name: dict[str, str] = {}  # normalized name -> domain key

    def seed(self, prospects: list[Prospect]) -> None:
        for p in prospects:
            self.add(p)

    def _key(self, p: Prospect) -> str:
        dom = normalize_domain(p.domain or p.website)
        if dom:
            return dom
        return "name:" + normalize_company_name(p.company_name)

    def contains(self, p: Prospect) -> bool:
        key = self._key(p)
        if key in self.by_domain:
            return True
        norm = normalize_company_name(p.company_name)
        return norm in self.by_name

    def add(self, p: Prospect) -> Prospect:
        """Add or merge a prospect. Returns the canonical stored prospect."""
        key = self._key(p)
        norm_name = normalize_company_name(p.company_name)

        existing = self.by_domain.get(key)
        if existing is None and norm_name in self.by_name:
            existing = self.by_domain.get(self.by_name[norm_name])

        if existing:
            merged = existing.merge(p)
            self.by_domain[key] = merged
            if norm_name:
                self.by_name[norm_name] = key
            return merged

        self.by_domain[key] = p
        if norm_name:
            self.by_name[norm_name] = key
        return p

    def all(self) -> list[Prospect]:
        return list(self.by_domain.values())
