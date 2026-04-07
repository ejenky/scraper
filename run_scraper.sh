#!/bin/bash
# Run the scraper for all verticals
cd "$(dirname "$0")"
source venv/bin/activate
echo "🚀 Starting prospect discovery for all verticals..."
python cli.py discover --vertical all --pages 2
echo ""
echo "✅ Discovery complete. Run enrichment:"
echo "  python cli.py enrich --input data/prospects.csv --deep"
