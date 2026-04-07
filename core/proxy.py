"""Proxy rotation manager."""
from __future__ import annotations

import random
from pathlib import Path
from typing import Optional

from loguru import logger

from config.settings import (
    BRIGHTDATA_PASSWORD,
    BRIGHTDATA_USERNAME,
    PROJECT_ROOT,
    SCRAPER_API_KEY,
)


class ProxyManager:
    def __init__(self) -> None:
        self.proxies: list[str] = []
        self._load()

    def _load(self) -> None:
        if SCRAPER_API_KEY:
            self.proxies.append(
                f"http://scraperapi:{SCRAPER_API_KEY}@proxy-server.scraperapi.com:8001"
            )
        if BRIGHTDATA_USERNAME and BRIGHTDATA_PASSWORD:
            self.proxies.append(
                f"http://{BRIGHTDATA_USERNAME}:{BRIGHTDATA_PASSWORD}@brd.superproxy.io:22225"
            )
        proxy_file = PROJECT_ROOT / "config" / "proxies.txt"
        if proxy_file.exists():
            for line in proxy_file.read_text().strip().splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    self.proxies.append(line)
        if self.proxies:
            logger.info(f"Loaded {len(self.proxies)} proxies")

    def get(self) -> Optional[str]:
        if not self.proxies:
            return None
        return random.choice(self.proxies)

    def as_httpx_proxies(self) -> Optional[dict]:
        p = self.get()
        if not p:
            return None
        return {"http://": p, "https://": p}
