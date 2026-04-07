"""Pydantic data models for prospects."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Vertical(str, Enum):
    CASINO = "casino"
    SPORTS_BETTING = "sports_betting"
    CRYPTO = "crypto"
    MOBILE_GAMES = "mobile_games"
    APPS = "apps"
    PREDICTION_MARKETS = "prediction_markets"
    ESPORTS = "esports"
    FANTASY_SPORTS = "fantasy_sports"
    UNKNOWN = "unknown"


class Source(str, Enum):
    GOOGLE_SEARCH = "google_search"
    GOOGLE_MAPS = "google_maps"
    GOOGLE_PLAY = "google_play"
    DIRECTORY = "directory"
    LINKEDIN = "linkedin"
    MANUAL = "manual"


class ContactPerson(BaseModel):
    name: str
    title: str = ""
    email: str = ""
    linkedin_url: str = ""


class SocialLinks(BaseModel):
    linkedin: str = ""
    twitter: str = ""
    instagram: str = ""
    telegram: str = ""
    discord: str = ""
    facebook: str = ""
    youtube: str = ""
    tiktok: str = ""

    def count(self) -> int:
        return sum(1 for v in self.model_dump().values() if v)


class Prospect(BaseModel):
    # Identity
    company_name: str
    domain: str = ""
    website: str = ""

    # Classification
    vertical: Vertical = Vertical.UNKNOWN
    source: Source = Source.MANUAL
    source_query: str = ""

    # Contact info
    primary_email: str = ""
    all_emails: list[str] = Field(default_factory=list)
    phone: str = ""

    # People
    contacts: list[ContactPerson] = Field(default_factory=list)

    # Social
    socials: SocialLinks = Field(default_factory=SocialLinks)

    # Business intel
    description: str = ""
    has_affiliate_program: bool = False
    affiliate_url: str = ""
    company_size: str = ""

    # Google Play specific
    app_name: str = ""
    app_id: str = ""
    developer_name: str = ""
    developer_email: str = ""
    installs: str = ""
    app_rating: float = 0.0

    # Google Maps specific
    maps_rating: float = 0.0
    maps_reviews_count: int = 0
    address: str = ""
    maps_category: str = ""

    # Metadata
    scraped_at: datetime = Field(default_factory=datetime.now)
    enriched: bool = False
    enriched_at: Optional[datetime] = None
    score: int = 0

    def merge(self, other: "Prospect") -> "Prospect":
        """Merge another prospect into this one, preferring non-empty values."""
        data = self.model_dump()
        other_data = other.model_dump()
        for key, val in other_data.items():
            if key in ("scraped_at", "enriched_at"):
                continue
            cur = data.get(key)
            if isinstance(val, list):
                merged = list(cur or [])
                for item in val:
                    if item not in merged:
                        merged.append(item)
                data[key] = merged
            elif isinstance(val, dict):
                merged = dict(cur or {})
                for k, v in val.items():
                    if v and not merged.get(k):
                        merged[k] = v
                data[key] = merged
            elif isinstance(val, bool):
                data[key] = bool(cur) or bool(val)
            elif isinstance(val, (int, float)):
                if not cur:
                    data[key] = val
            else:
                if not cur:
                    data[key] = val
        return Prospect(**data)
