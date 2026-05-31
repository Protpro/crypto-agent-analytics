#!/bin/bash
# Setup crypto-agent-analytics environment

set -e

echo "🔧 Setting up crypto-agent-analytics..."

# Check Python
python3 --version || { echo "❌ Python 3.11+ required"; exit 1; }

# Create venv
python3 -m venv venv
source venv/bin/activate

# Install deps
pip install -r requirements.txt

# Copy config
if [ ! -f config/settings.yaml ]; then
    cp config/settings.example.yaml config/settings.yaml
    echo "📝 Created config/settings.yaml — edit with your credentials"
fi

# Check Redis
redis-cli ping 2>/dev/null || echo "⚠️  Redis not running — install or start redis-server"

echo "✅ Setup complete!"
echo "   Edit config/settings.yaml with your RPC endpoints"
echo "   Run: python run_all.py --config config/settings.yaml"
