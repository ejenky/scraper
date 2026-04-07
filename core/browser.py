"""Unified browser/HTTP fetch helpers. Wraps Scrapling with a safe fallback."""
from __future__ import annotations

from typing import Any, Optional

from loguru import logger

from config.settings import DEFAULT_TIMEOUT
from core.rate_limiter import wait_for

try:
    from scrapling.fetchers import Fetcher, StealthyFetcher  # type: ignore
    _HAS_SCRAPLING = True
except Exception:  # pragma: no cover
    _HAS_SCRAPLING = False
    Fetcher = None  # type: ignore
    StealthyFetcher = None  # type: ignore


def fetch(url: str, stealth: bool = False, timeout: int = DEFAULT_TIMEOUT) -> Optional[Any]:
    """Fetch a URL. Returns a Scrapling page object (has .css / .html_content / .text).

    Falls back to httpx if Scrapling is unavailable; returns a compatible shim.
    """
    if not url:
        return None
    wait_for(url)
    try:
        if _HAS_SCRAPLING:
            if stealth:
                return StealthyFetcher.fetch(
                    url, headless=True, network_idle=True, timeout=timeout * 1000
                )
            return Fetcher.get(url, stealthy_headers=True, timeout=timeout)
    except Exception as e:
        logger.debug(f"Scrapling fetch failed for {url}: {e}")

    # Fallback: httpx + lightweight shim
    try:
        import httpx

        resp = httpx.get(
            url,
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0 Safari/537.36"
                )
            },
        )
        return _HttpxPage(str(resp.url), resp.text, resp.status_code)
    except Exception as e:
        logger.debug(f"httpx fetch failed for {url}: {e}")
        return None


class _HttpxPage:
    """Minimal shim so callers can use .html_content and .text uniformly."""

    def __init__(self, url: str, html: str, status: int) -> None:
        self.url = url
        self.status = status
        self.html_content = html
        self.body = html
        self._text: Optional[str] = None

    @property
    def text(self) -> str:
        if self._text is None:
            import re

            self._text = re.sub(r"<[^>]+>", " ", self.html_content)
            self._text = re.sub(r"\s+", " ", self._text).strip()
        return self._text

    def css(self, selector: str) -> list:
        return []

    def css_first(self, selector: str):
        return None
