#!/bin/bash
# Start the dashboard
cd "$(dirname "$0")"
source venv/bin/activate
echo "🚀 Starting dashboard on port 8501..."
echo "Access at: http://$(curl -s ifconfig.me 2>/dev/null || echo 'your-server-ip'):8501"
streamlit run dashboard.py --server.port 8501 --server.address 0.0.0.0
