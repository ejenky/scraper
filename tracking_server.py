"""FastAPI tracking pixel + click-redirect server.

Run:
    uvicorn tracking_server:app --host 0.0.0.0 --port 8502

Endpoints:
    GET /t/<tracking_id>.png   -- 1x1 transparent tracking pixel (logs 'open')
    GET /c/<tracking_id>?url=  -- click redirect (logs 'click')
    GET /u/<tracking_id>       -- unsubscribe link
    GET /health                -- liveness probe
"""
from __future__ import annotations

import base64
import sqlite3
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from outreach.config import OUTREACH_DB

app = FastAPI(title="Rocket Brands Tracking")

# 1x1 transparent PNG
PIXEL = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4"
    "2mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
)

NO_CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate, private, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}


def _db() -> sqlite3.Connection:
    Path(OUTREACH_DB).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(OUTREACH_DB))
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _log_event(tracking_id: str, event_type: str, ip: str, ua: str, metadata: str = "") -> None:
    now = datetime.now().isoformat()
    try:
        conn = _db()
        conn.execute(
            """INSERT INTO tracking_events (tracking_id, event_type, ip, user_agent, timestamp, metadata)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (tracking_id, event_type, ip, ua, now, metadata),
        )
        if event_type == "open":
            conn.execute(
                """UPDATE emails SET status = 'opened', opened_at = COALESCE(opened_at, ?),
                                      opened_count = opened_count + 1
                   WHERE tracking_id = ? AND status NOT IN ('replied','unsubscribed','bounced')""",
                (now, tracking_id),
            )
        elif event_type == "click":
            conn.execute(
                """UPDATE emails SET status = 'clicked', clicked_at = COALESCE(clicked_at, ?),
                                      clicked_count = clicked_count + 1
                   WHERE tracking_id = ? AND status NOT IN ('replied','unsubscribed','bounced')""",
                (now, tracking_id),
            )
        conn.commit()
        conn.close()
    except Exception:
        # Don't crash the server on logging errors — the user is waiting on a pixel
        pass


@app.get("/t/{tracking_id}.png")
async def track_open(tracking_id: str, request: Request) -> Response:
    _log_event(
        tracking_id,
        "open",
        request.client.host if request.client else "",
        request.headers.get("user-agent", ""),
    )
    return Response(content=PIXEL, media_type="image/png", headers=NO_CACHE_HEADERS)


@app.get("/c/{tracking_id}")
async def track_click(tracking_id: str, request: Request) -> Response:
    url = request.query_params.get("url", "")
    _log_event(
        tracking_id,
        "click",
        request.client.host if request.client else "",
        request.headers.get("user-agent", ""),
        metadata=url,
    )
    if url:
        return RedirectResponse(url=url, status_code=302)
    return Response(status_code=204)


@app.get("/u/{tracking_id}")
async def unsubscribe(tracking_id: str) -> HTMLResponse:
    """Self-serve unsubscribe link."""
    try:
        conn = _db()
        row = conn.execute(
            "SELECT prospect_email FROM emails WHERE tracking_id = ? LIMIT 1",
            (tracking_id,),
        ).fetchone()
        if row and row[0]:
            email = row[0]
            conn.execute(
                "INSERT OR REPLACE INTO unsubscribes (email, unsubscribed_at) VALUES (?, ?)",
                (email.lower(), datetime.now().isoformat()),
            )
            conn.execute(
                "UPDATE emails SET status = 'unsubscribed' WHERE prospect_email = ?",
                (email.lower(),),
            )
            conn.commit()
        conn.close()
    except Exception:
        pass
    return HTMLResponse(
        "<html><body style='font-family:sans-serif;padding:40px;max-width:500px'>"
        "<h2>You've been unsubscribed.</h2>"
        "<p>You won't receive any more emails from us. Sorry for the interruption.</p>"
        "</body></html>"
    )


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "rocket-tracking"}
