"""Decision-maker name/title extraction."""
from __future__ import annotations

import re

from config.settings import MAX_CONTACTS_PER_PROSPECT
from config.verticals import TARGET_TITLES
from core.models import ContactPerson

NAME_TITLE_RE = re.compile(
    r"([A-Z][a-z]+(?:\s[A-Z][a-z]+){1,3})\s*[-–—,:]\s*([A-Z][\w\s&/]{3,60})"
)


def matches_target_title(title: str) -> bool:
    t = (title or "").lower()
    return any(kw in t for kw in TARGET_TITLES)


def extract_contacts(text: str, max_contacts: int = MAX_CONTACTS_PER_PROSPECT) -> list[ContactPerson]:
    contacts: list[ContactPerson] = []
    seen: set[str] = set()
    for m in NAME_TITLE_RE.finditer(text or ""):
        name = m.group(1).strip()
        title = m.group(2).strip()
        if name in seen:
            continue
        if not matches_target_title(title):
            continue
        seen.add(name)
        contacts.append(ContactPerson(name=name, title=title))
        if len(contacts) >= max_contacts:
            break
    return contacts
