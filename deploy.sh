#!/bin/bash
# Rocket Brands Prospect Scraper — Deploy Script
# Usage: bash deploy.sh

set -e

echo "🚀 Deploying Rocket Brands Prospect Scraper..."

# Install system deps
apt-get update -qq
apt-get install -y -qq python3-venv python3-pip

# Setup Python env
cd "$(dirname "$0")"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q

# Install Playwright for Scrapling stealth mode
playwright install chromium 2>/dev/null || echo "Playwright chromium install skipped"
playwright install-deps 2>/dev/null || echo "Playwright deps install skipped"

# Create .env if not exists
if [ ! -f .env ]; then
    cat > .env << 'ENVEOF'
# Scraper
SERPER_API_KEY=
PROXYCURL_API_KEY=
LINKEDIN_COOKIE=
SCRAPER_API_KEY=
OPENAI_API_KEY=

# Outreach
GROQ_API_KEY=
GMAIL_USER_1=
GMAIL_APP_PASSWORD_1=
GMAIL_DISPLAY_NAME_1=Eric @ First LLC
GMAIL_USER_2=
GMAIL_APP_PASSWORD_2=
GMAIL_DISPLAY_NAME_2=Eric @ Second LLC
TRACKING_DOMAIN=159.65.184.35
TRACKING_PORT=8502
MAX_EMAILS_PER_DAY_PER_ACCOUNT=25
MAX_EMAILS_PER_HOUR_PER_ACCOUNT=8
MIN_DELAY_BETWEEN_EMAILS=120
MAX_DELAY_BETWEEN_EMAILS=300
ENVEOF
    echo "Created .env — add your API keys"
fi

# Create logs dir
mkdir -p logs data

# Open firewall for dashboards + tracking server
ufw allow 8501 2>/dev/null || true   # scraper dashboard
ufw allow 8502 2>/dev/null || true   # tracking server
ufw allow 8503 2>/dev/null || true   # outreach dashboard

echo ""
echo "✅ Deployment complete!"
echo ""
echo "Commands:"
echo "  source venv/bin/activate"
echo "  python cli.py discover --vertical casino --pages 2        # Scrape casino vertical"
echo "  python cli.py discover --vertical all --pages 2           # Scrape all verticals"
echo "  python cli.py enrich --input data/prospects.csv --deep    # Enrich with deep crawl"
echo "  streamlit run dashboard.py --server.port 8501 --server.address 0.0.0.0       # Scraper dashboard"
echo ""
echo "Outreach:"
echo "  python outreach_cli.py generate --campaign 'Casino Q2' --vertical casino --min-score 20"
echo "  python outreach_cli.py preview --campaign 'Casino Q2'"
echo "  python outreach_cli.py send --campaign 'Casino Q2' --dry-run"
echo "  python outreach_cli.py send --campaign 'Casino Q2'"
echo "  python outreach_cli.py followup"
echo "  python outreach_cli.py health"
echo "  uvicorn tracking_server:app --host 0.0.0.0 --port 8502 &"
echo "  streamlit run outreach_dashboard.py --server.port 8503 --server.address 0.0.0.0"
echo ""
echo "Run scraper in background with tmux:"
echo "  tmux new -s scraper"
echo "  python cli.py discover --vertical all --pages 3"
echo "  # Ctrl+B, D to detach"
echo ""
echo "Dashboard will be at: http://$(curl -s ifconfig.me 2>/dev/null || echo 'your-server-ip'):8501"
