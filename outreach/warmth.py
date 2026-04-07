"""Sending rate controller + sender reputation health checks."""
from __future__ import annotations

from dataclasses import dataclass

from outreach.config import (
    MAX_EMAILS_PER_DAY_PER_ACCOUNT,
    MAX_EMAILS_PER_HOUR_PER_ACCOUNT,
)
from outreach.storage import connect, sends_last_hour, sends_today


@dataclass
class AccountHealth:
    email: str
    sends_today: int
    sends_hour: int
    daily_cap: int
    hourly_cap: int
    daily_remaining: int
    hourly_remaining: int

    @property
    def healthy(self) -> bool:
        return self.daily_remaining > 0 and self.hourly_remaining > 0


def check_account_health(sender_email: str) -> AccountHealth:
    conn = connect()
    try:
        daily = sends_today(conn, sender_email)
        hourly = sends_last_hour(conn, sender_email)
    finally:
        conn.close()
    return AccountHealth(
        email=sender_email,
        sends_today=daily,
        sends_hour=hourly,
        daily_cap=MAX_EMAILS_PER_DAY_PER_ACCOUNT,
        hourly_cap=MAX_EMAILS_PER_HOUR_PER_ACCOUNT,
        daily_remaining=max(0, MAX_EMAILS_PER_DAY_PER_ACCOUNT - daily),
        hourly_remaining=max(0, MAX_EMAILS_PER_HOUR_PER_ACCOUNT - hourly),
    )


def check_all(accounts: list[str]) -> list[AccountHealth]:
    return [check_account_health(a) for a in accounts]
