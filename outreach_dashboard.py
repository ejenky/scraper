"""Rocket Brands Outreach Dashboard.

Run:
    streamlit run outreach_dashboard.py --server.port 8503 --server.address 0.0.0.0
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
DB_PATH = PROJECT_ROOT / "data" / "outreach.db"

st.set_page_config(
    page_title="Rocket Brands — Outreach",
    page_icon="✉️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .stApp { background-color: #0e1117; }
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        padding: 18px 20px;
        border-radius: 12px;
        border: 1px solid #233047;
        box-shadow: 0 2px 12px rgba(0, 212, 255, 0.08);
    }
    [data-testid="stMetricLabel"] { color: #8fa3c4 !important; }
    [data-testid="stMetricValue"] { color: #00d4ff !important; font-weight: 700; }
    h1, h2, h3 { color: #e8eefc; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=15)
def load_campaigns(db_mtime: float) -> pd.DataFrame:
    _ = db_mtime
    if not DB_PATH.exists():
        return pd.DataFrame()
    conn = sqlite3.connect(str(DB_PATH))
    try:
        df = pd.read_sql_query(
            "SELECT * FROM campaigns ORDER BY created_at DESC", conn
        )
    finally:
        conn.close()
    return df


@st.cache_data(ttl=15)
def load_emails(db_mtime: float, campaign_id: str | None = None) -> pd.DataFrame:
    _ = db_mtime
    if not DB_PATH.exists():
        return pd.DataFrame()
    conn = sqlite3.connect(str(DB_PATH))
    try:
        if campaign_id:
            df = pd.read_sql_query(
                "SELECT * FROM emails WHERE campaign_id = ? ORDER BY created_at DESC",
                conn, params=(campaign_id,),
            )
        else:
            df = pd.read_sql_query("SELECT * FROM emails ORDER BY created_at DESC", conn)
    finally:
        conn.close()
    return df


@st.cache_data(ttl=15)
def load_send_log(db_mtime: float) -> pd.DataFrame:
    _ = db_mtime
    if not DB_PATH.exists():
        return pd.DataFrame()
    conn = sqlite3.connect(str(DB_PATH))
    try:
        df = pd.read_sql_query("SELECT * FROM send_log ORDER BY sent_at DESC LIMIT 2000", conn)
    finally:
        conn.close()
    return df


def _pct(num: int, denom: int) -> str:
    return f"{100 * num / denom:.1f}%" if denom else "0%"


# --- Sidebar ---
with st.sidebar:
    st.markdown("## ✉️ Rocket Brands")
    st.caption("Outreach Dashboard")
    st.divider()
    auto_refresh = st.checkbox("Auto-refresh (30s)", value=False)
    if DB_PATH.exists():
        st.caption(f"📄 `{DB_PATH.relative_to(PROJECT_ROOT)}`")
    else:
        st.caption("📄 No outreach.db yet")

st.title("✉️ Rocket Brands — Outreach Dashboard")

if not DB_PATH.exists():
    st.warning(
        "No outreach database found yet. Generate emails first:\n\n"
        "```bash\n"
        "python outreach_cli.py generate --campaign \"Casino Q2\" --vertical casino --min-score 20\n"
        "```"
    )
    if auto_refresh:
        import time; time.sleep(30); st.rerun()
    st.stop()

mtime = DB_PATH.stat().st_mtime
campaigns_df = load_campaigns(mtime)

if campaigns_df.empty:
    st.info("Database exists but no campaigns yet. Run `outreach_cli.py generate` to create one.")
    st.stop()

# --- Campaign selector ---
camp_names = ["All campaigns"] + campaigns_df["name"].tolist()
selected = st.selectbox("Campaign", camp_names)

if selected == "All campaigns":
    campaign_id = None
    campaign_row = None
else:
    campaign_row = campaigns_df[campaigns_df["name"] == selected].iloc[0]
    campaign_id = campaign_row["id"]

emails_df = load_emails(mtime, campaign_id)

# --- Top metrics ---
total = len(emails_df)
sent = int((emails_df["status"].isin(["sent", "opened", "clicked", "replied"])).sum()) if total else 0
opens = int((emails_df.get("opened_count", 0) > 0).sum()) if total else 0
clicks = int((emails_df.get("clicked_count", 0) > 0).sum()) if total else 0
replies = int((emails_df["status"] == "replied").sum()) if total else 0
bounces = int((emails_df["status"] == "bounced").sum()) if total else 0

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Sent", f"{sent:,}")
c2.metric("Opens", f"{opens:,}", _pct(opens, sent))
c3.metric("Open Rate", _pct(opens, sent))
c4.metric("Clicks", f"{clicks:,}", _pct(clicks, opens))
c5.metric("Replies", f"{replies:,}", _pct(replies, sent))
c6.metric("Reply Rate", _pct(replies, sent))

if bounces > 0:
    bounce_rate = 100 * bounces / sent if sent else 0
    if bounce_rate > 5:
        st.error(f"⚠️ Bounce rate {bounce_rate:.1f}% exceeds 5% — pause campaign and clean list")
    else:
        st.caption(f"Bounces: {bounces} ({bounce_rate:.1f}%)")

st.divider()

# --- Timeline chart ---
st.subheader("📈 Timeline")
if not emails_df.empty and "sent_at" in emails_df.columns:
    timeline = emails_df.copy()
    timeline["sent_at"] = pd.to_datetime(timeline["sent_at"], errors="coerce")
    timeline = timeline.dropna(subset=["sent_at"])
    if not timeline.empty:
        timeline["date"] = timeline["sent_at"].dt.date
        agg = timeline.groupby("date").agg(
            sent=("id", "count"),
            opened=("opened_count", lambda s: int((s > 0).sum())),
            clicked=("clicked_count", lambda s: int((s > 0).sum())),
        )
        st.line_chart(agg)
    else:
        st.caption("No sent emails yet")
else:
    st.caption("No data yet")

st.divider()

# --- Two columns: Vertical performance + Sender usage ---
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("📊 Vertical Performance")
    if not emails_df.empty and "prospect_vertical" in emails_df.columns:
        vert = emails_df.groupby("prospect_vertical").agg(
            total=("id", "count"),
            opens=("opened_count", lambda s: int((s > 0).sum())),
            replies=("status", lambda s: int((s == "replied").sum())),
        )
        vert["open_rate_%"] = (100 * vert["opens"] / vert["total"]).round(1)
        vert["reply_rate_%"] = (100 * vert["replies"] / vert["total"]).round(1)
        st.dataframe(vert, use_container_width=True)
    else:
        st.caption("No data")

with col_right:
    st.subheader("📮 Sender Account Usage")
    send_log = load_send_log(mtime)
    if not send_log.empty:
        today = datetime.now().strftime("%Y-%m-%d")
        today_counts = (
            send_log[send_log["date"] == today]
            .groupby("sender_email")
            .size()
            .reset_index(name="today")
        )
        total_counts = (
            send_log.groupby("sender_email").size().reset_index(name="total_all_time")
        )
        usage = today_counts.merge(total_counts, on="sender_email", how="outer").fillna(0)
        usage["today"] = usage["today"].astype(int)
        usage["total_all_time"] = usage["total_all_time"].astype(int)
        usage["daily_cap"] = 25
        usage["remaining"] = (usage["daily_cap"] - usage["today"]).clip(lower=0)
        st.dataframe(usage, use_container_width=True, hide_index=True)
    else:
        st.caption("No sends yet")

st.divider()

# --- Email table with filters ---
st.subheader("📧 Emails")
if not emails_df.empty:
    f1, f2, f3 = st.columns(3)
    with f1:
        statuses = ["All"] + sorted(emails_df["status"].dropna().unique().tolist())
        f_status = st.selectbox("Status", statuses)
    with f2:
        steps = ["All"] + sorted(emails_df["sequence_step"].dropna().unique().tolist())
        f_step = st.selectbox("Sequence step", steps)
    with f3:
        verts = ["All"] + sorted(emails_df["prospect_vertical"].dropna().unique().tolist())
        f_vert = st.selectbox("Vertical", verts)

    view = emails_df.copy()
    if f_status != "All":
        view = view[view["status"] == f_status]
    if f_step != "All":
        view = view[view["sequence_step"] == f_step]
    if f_vert != "All":
        view = view[view["prospect_vertical"] == f_vert]

    show_cols = [
        "prospect_company", "prospect_email", "prospect_vertical", "subject",
        "status", "sequence_step", "sent_at", "opened_count", "clicked_count", "sender_email",
    ]
    show_cols = [c for c in show_cols if c in view.columns]
    st.dataframe(view[show_cols], use_container_width=True, height=420, hide_index=True)
    st.caption(f"Showing {len(view)} of {len(emails_df)} emails")

st.divider()

# --- Action items ---
st.subheader("🎯 Action Items")
colA, colB = st.columns(2)

with colA:
    st.markdown("**Due for follow-up (next 24h)**")
    if not emails_df.empty and "sent_at" in emails_df.columns:
        e = emails_df.copy()
        e["sent_at"] = pd.to_datetime(e["sent_at"], errors="coerce")
        now = datetime.now()
        def _days_due(step: str) -> int:
            return {"initial": 3, "followup_1": 7, "followup_2": 14}.get(step, 999)
        e["days_since_sent"] = (now - e["sent_at"]).dt.days
        e["trigger_days"] = e["sequence_step"].map(_days_due)
        due = e[
            (e["status"].isin(["sent", "opened", "clicked"]))
            & (e["days_since_sent"] >= e["trigger_days"] - 1)
            & (e["sequence_step"] != "followup_3")
        ]
        if not due.empty:
            st.dataframe(
                due[["prospect_company", "prospect_email", "sequence_step", "days_since_sent"]],
                use_container_width=True, hide_index=True,
            )
        else:
            st.caption("Nothing due for follow-up")

with colB:
    st.markdown("**Recent opens (prioritize these)**")
    if not emails_df.empty and "opened_at" in emails_df.columns:
        opened = emails_df[emails_df["opened_count"] > 0].copy()
        opened["opened_at"] = pd.to_datetime(opened["opened_at"], errors="coerce")
        opened = opened.sort_values("opened_at", ascending=False).head(10)
        if not opened.empty:
            st.dataframe(
                opened[["prospect_company", "prospect_email", "opened_count", "opened_at"]],
                use_container_width=True, hide_index=True,
            )
        else:
            st.caption("No opens yet")

# --- Auto-refresh ---
if auto_refresh:
    import time
    time.sleep(30)
    st.rerun()
