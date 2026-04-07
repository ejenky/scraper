"""Per-domain rate limiter with jitter."""
from __future__ import annotations

import random
import time
from urllib.parse import urlparse

from config.settings import RATE_LIMITS


class RateLimiter:
    def __init__(self, limits: dict | None = None) -> None:
        self.limits = limits or RATE_LIMITS
        self._last_hit: dict[str, float] = {}

    def _key(self, url: str) -> str:
        try:
            host = urlparse(url).netloc.lower()
        except Exception:
            host = "default"
        host = host.replace("www.", "")
        for known in self.limits:
            if known != "default" and known in host:
                return known
        return "default"

    def wait(self, url: str) -> None:
        key = self._key(url)
        cfg = self.limits.get(key, self.limits["default"])
        delay = random.uniform(cfg["min_delay"], cfg["max_delay"])
        last = self._last_hit.get(key, 0)
        elapsed = time.time() - last
        remaining = delay - elapsed
        if remaining > 0:
            time.sleep(remaining)
        self._last_hit[key] = time.time()


_global = RateLimiter()


def wait_for(url: str) -> None:
    _global.wait(url)
