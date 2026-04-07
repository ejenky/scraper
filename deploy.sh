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
SERPER_API_KEY=
PROXYCURL_API_KEY=
LINKEDIN_COOKIE=
SCRAPER_API_KEY=
OPENAI_API_KEY=
ENVEOF
    echo "Created .env — add your API keys"
fi

# Create logs dir
mkdir -p logs data

# Open firewall for dashboard
ufw allow 8501 2>/dev/null || true

echo ""
echo "✅ Deployment complete!"
echo ""
echo "Commands:"
echo "  source venv/bin/activate"
echo "  python cli.py discover --vertical casino --pages 2        # Scrape casino vertical"
echo "  python cli.py discover --vertical all --pages 2           # Scrape all verticals"
echo "  python cli.py enrich --input data/prospects.csv --deep    # Enrich with deep crawl"
echo "  streamlit run dashboard.py --server.port 8501 --server.address 0.0.0.0  # Start dashboard"
echo ""
echo "Run scraper in background with tmux:"
echo "  tmux new -s scraper"
echo "  python cli.py discover --vertical all --pages 3"
echo "  # Ctrl+B, D to detach"
echo ""
echo "Dashboard will be at: http://$(curl -s ifconfig.me 2>/dev/null || echo 'your-server-ip'):8501"
