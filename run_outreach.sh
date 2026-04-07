#!/bin/bash
# Start tracking server + outreach dashboard in background
cd "$(dirname "$0")"
source venv/bin/activate

mkdir -p logs

echo "🚀 Starting tracking server on port 8502..."
nohup uvicorn tracking_server:app --host 0.0.0.0 --port 8502 > logs/tracking.log 2>&1 &
echo "   PID $! (log: logs/tracking.log)"

echo "🚀 Starting outreach dashboard on port 8503..."
nohup streamlit run outreach_dashboard.py --server.port 8503 --server.address 0.0.0.0 \
    > logs/outreach_dashboard.log 2>&1 &
echo "   PID $! (log: logs/outreach_dashboard.log)"

IP=$(curl -s ifconfig.me 2>/dev/null || echo 'your-server-ip')
echo ""
echo "Tracking:  http://${IP}:8502/health"
echo "Dashboard: http://${IP}:8503"
echo ""
echo "CLI examples:"
echo "  python outreach_cli.py generate --campaign 'Casino Q2' --vertical casino --min-score 20"
echo "  python outreach_cli.py preview --campaign 'Casino Q2'"
echo "  python outreach_cli.py send --campaign 'Casino Q2' --dry-run"
echo "  python outreach_cli.py send --campaign 'Casino Q2'"
echo "  python outreach_cli.py followup --auto-send"
