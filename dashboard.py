"""Rocket Brands — Streamlit Prospect Dashboard.

Single-file Streamlit dashboard. Reads from the same CSV the scraper writes to
(default: data/prospects.csv). Gracefully handles missing columns from older runs.

Run:
    streamlit run dashboard.py --server.port 8501 --server.address 0.0.0.0
"""
from __future__ import annotations

from pathlib import Path

import polars as pl
import streamlit as st

# --- Paths ---
PROJECT_ROOT = Path(__file__).resolve().parent
CANDIDATE_PATHS = [
    PROJECT_ROOT / "data" / "prospects.csv",
    PROJECT_ROOT / "prospects.csv",
]

# --- Page config ---
st.set_page_config(
    page_title="Rocket Brands — Prospect Dashboard",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Custom CSS ---
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
    .hot-row {
        padding: 10px 14px;
        margin: 6px 0;
        background: linear-gradient(90deg, #1a1a2e 0%, #16213e 100%);
        border-left: 3px solid #00d4ff;
        border-radius: 8px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# --- Data loading ---

EXPECTED_COLS = [
    "company_name", "domain", "website", "vertical", "source", "source_query",
    "primary_email", "all_emails", "phone",
    "contact_1_name", "contact_1_title", "contact_1_email", "contact_1_linkedin",
    "contact_2_name", "contact_2_title", "contact_2_email", "contact_2_linkedin",
    "linkedin", "twitter", "instagram", "telegram", "discord",
    "facebook", "youtube", "tiktok",
    "description", "has_affiliate_program", "affiliate_url", "company_size",
    "app_name", "app_id", "developer_name", "developer_email", "installs", "app_rating",
    "maps_rating", "maps_reviews_count", "address", "maps_category",
    "score", "scraped_at", "enriched",
]


def find_csv() -> Path | None:
    for p in CANDIDATE_PATHS:
        if p.exists() and p.stat().st_size > 0:
            return p
    return None


@st.cache_data(ttl=30)
def load_data(path_str: str, mtime: float) -> pl.DataFrame:
    """Load the prospects CSV into a Polars DataFrame.

    mtime is part of the cache key so the cache invalidates when the file
    is updated by the scraper.
    """
    _ = mtime  # used only for cache key
    df = pl.read_csv(
        path_str,
        infer_schema_length=2000,
        ignore_errors=True,
        truncate_ragged_lines=True,
    )
    # Ensure all expected columns exist so downstream code never KeyErrors
    for col in EXPECTED_COLS:
        if col not in df.columns:
            df = df.with_columns(pl.lit("").alias(col))

    # Cast numeric columns safely
    def _to_int(col: str) -> pl.Expr:
        return (
            pl.col(col)
            .cast(pl.Utf8, strict=False)
            .str.strip_chars()
            .str.replace_all(r"[^0-9\-]", "")
            .cast(pl.Int64, strict=False)
            .fill_null(0)
            .alias(col)
        )

    def _to_float(col: str) -> pl.Expr:
        return (
            pl.col(col)
            .cast(pl.Utf8, strict=False)
            .str.strip_chars()
            .cast(pl.Float64, strict=False)
            .fill_null(0.0)
            .alias(col)
        )

    df = df.with_columns([
        _to_int("score"),
        _to_int("maps_reviews_count"),
        _to_float("app_rating"),
        _to_float("maps_rating"),
    ])
    # Normalize string columns (fill nulls)
    str_cols = [c for c in EXPECTED_COLS if c not in ("score", "maps_reviews_count", "app_rating", "maps_rating")]
    df = df.with_columns([pl.col(c).cast(pl.Utf8, strict=False).fill_null("") for c in str_cols if c in df.columns])
    return df


# --- Sidebar ---
with st.sidebar:
    st.markdown("## 🚀 Rocket Brands")
    st.caption("Prospect Dashboard")
    st.divider()
    auto_refresh = st.checkbox("Auto-refresh (30s)", value=False)
    csv_path = find_csv()
    if csv_path:
        st.caption(f"📄 `{csv_path.relative_to(PROJECT_ROOT)}`")
    else:
        st.caption("📄 No CSV found yet")
    st.divider()
    st.markdown("**Rocket Brands Media**")
    st.caption("Media buying for iGaming, crypto, apps & games")


# --- Main ---
st.title("🚀 Rocket Brands — Prospect Dashboard")

csv_path = find_csv()
if csv_path is None:
    st.warning(
        "No prospects CSV found yet. Run the scraper first:\n\n"
        "```bash\n"
        "python cli.py discover --vertical all --pages 2\n"
        "```\n\n"
        f"Looking in: `{CANDIDATE_PATHS[0]}` and `{CANDIDATE_PATHS[1]}`"
    )
    if auto_refresh:
        import time
        time.sleep(30)
        st.rerun()
    st.stop()

try:
    df = load_data(str(csv_path), csv_path.stat().st_mtime)
except Exception as e:
    st.error(f"Failed to load CSV: {e}")
    st.stop()

if df.height == 0:
    st.info("CSV exists but contains no prospects yet.")
    st.stop()

# Sidebar count
with st.sidebar:
    st.metric("Total prospects", f"{df.height:,}")


# --- Metrics row ---
total = df.height
with_email = df.filter(pl.col("primary_email") != "").height
with_contacts = df.filter(pl.col("contact_1_name") != "").height
with_affiliate = df.filter(
    (pl.col("has_affiliate_program") != "") & (pl.col("has_affiliate_program") != "False")
).height
avg_score = df.select(pl.col("score").mean()).item() or 0
hot_leads = df.filter(pl.col("score") >= 70).height


def _pct(n: int) -> str:
    return f"{100 * n / total:.0f}%" if total else "0%"


c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Total Prospects", f"{total:,}")
c2.metric("With Email", f"{with_email:,}", _pct(with_email))
c3.metric("With Contacts", f"{with_contacts:,}", _pct(with_contacts))
c4.metric("Affiliate Program", f"{with_affiliate:,}", _pct(with_affiliate))
c5.metric("Avg Score", f"{avg_score:.1f}")
c6.metric("🔥 Hot Leads", f"{hot_leads:,}", _pct(hot_leads))

st.divider()

# --- Filters ---
st.subheader("Filters")
f1, f2, f3 = st.columns(3)

with f1:
    verticals = ["All"] + sorted({v for v in df["vertical"].to_list() if v})
    sel_vertical = st.selectbox("Vertical", verticals)

with f2:
    sources = ["All"] + sorted({s for s in df["source"].to_list() if s})
    sel_source = st.selectbox("Source", sources)

with f3:
    min_score = st.slider("Min Score", 0, 100, 0)

email_only = st.checkbox("Only show prospects with emails", value=False)

# Apply filters
filtered = df
if sel_vertical != "All":
    filtered = filtered.filter(pl.col("vertical") == sel_vertical)
if sel_source != "All":
    filtered = filtered.filter(pl.col("source") == sel_source)
if min_score > 0:
    filtered = filtered.filter(pl.col("score") >= min_score)
if email_only:
    filtered = filtered.filter(pl.col("primary_email") != "")

filtered = filtered.sort("score", descending=True)

st.caption(f"Showing **{filtered.height:,}** of {total:,} prospects")

st.divider()

# --- Data table ---
st.subheader("Prospects")

display_cols = [
    "company_name", "vertical", "source", "primary_email", "website", "score",
    "has_affiliate_program", "contact_1_name", "contact_1_title",
    "developer_email", "installs", "phone",
]
display_cols = [c for c in display_cols if c in filtered.columns]

try:
    pandas_df = filtered.select(display_cols).to_pandas()
    st.dataframe(pandas_df, use_container_width=True, height=500, hide_index=True)
except Exception as e:
    st.error(f"Failed to render table: {e}")

st.divider()

# --- Charts ---
st.subheader("Breakdown")
ch1, ch2 = st.columns(2)

with ch1:
    st.caption("Prospects by Vertical")
    vert_counts = (
        filtered.group_by("vertical")
        .agg(pl.len().alias("count"))
        .sort("count", descending=True)
    )
    if vert_counts.height > 0:
        st.bar_chart(vert_counts.to_pandas().set_index("vertical"), color="#00d4ff")
    else:
        st.info("No data for selected filters")

with ch2:
    st.caption("Prospects by Source")
    src_counts = (
        filtered.group_by("source")
        .agg(pl.len().alias("count"))
        .sort("count", descending=True)
    )
    if src_counts.height > 0:
        st.bar_chart(src_counts.to_pandas().set_index("source"), color="#00d4ff")
    else:
        st.info("No data for selected filters")

# --- Score distribution ---
st.caption("Score Distribution")
score_buckets = (
    filtered.with_columns((pl.col("score") // 10 * 10).alias("bucket"))
    .group_by("bucket")
    .agg(pl.len().alias("count"))
    .sort("bucket")
)
if score_buckets.height > 0:
    st.bar_chart(score_buckets.to_pandas().set_index("bucket"), color="#00d4ff")

st.divider()

# --- Hot leads ---
st.subheader("🔥 Top 20 Hot Leads")
top = filtered.sort("score", descending=True).head(20)

if top.height == 0:
    st.info("No hot leads matching current filters")
else:
    for row in top.iter_rows(named=True):
        score = int(row.get("score") or 0)
        if score >= 70:
            indicator = "🟢"
        elif score >= 40:
            indicator = "🟡"
        else:
            indicator = "🔴"

        aff = "✓ Affiliate" if (row.get("has_affiliate_program") or "") not in ("", "False") else ""
        contact = row.get("contact_1_name") or ""
        title = row.get("contact_1_title") or ""
        contact_str = f"{contact} ({title})" if contact and title else contact or ""
        email = row.get("primary_email") or ""
        website = row.get("website") or ""
        vertical = row.get("vertical") or ""
        company = row.get("company_name") or ""

        st.markdown(
            f"""<div class="hot-row">
            <strong>{indicator} {company}</strong> &nbsp;·&nbsp;
            <em>{vertical}</em> &nbsp;·&nbsp;
            score <strong>{score}</strong> &nbsp;·&nbsp;
            {aff}<br>
            🌐 <a href="{website}" target="_blank">{website}</a> &nbsp;·&nbsp;
            ✉️ {email} &nbsp;·&nbsp;
            👤 {contact_str}
            </div>""",
            unsafe_allow_html=True,
        )

st.divider()

# --- Export ---
st.subheader("Export")
csv_bytes = filtered.write_csv().encode("utf-8")
st.download_button(
    label=f"⬇️  Download filtered CSV ({filtered.height:,} prospects)",
    data=csv_bytes,
    file_name="prospects_filtered.csv",
    mime="text/csv",
)
st.caption(f"Exporting {filtered.height:,} prospects matching current filters")


# --- Auto-refresh ---
if auto_refresh:
    import time
    time.sleep(30)
    st.rerun()
