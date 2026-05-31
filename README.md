# crypto-agent-analytics

Autonomous AI agents for on-chain cryptocurrency analytics. Real-time whale tracking, smart money flow detection, and multi-chain transaction monitoring powered by transformer models accelerated on AMD ROCm.

## Overview

Multi-agent system that monitors EVM chains in real-time, detects whale movements, classifies wallet behavior, and triggers alerts. Each agent runs independently with shared state via Redis Streams.

## Architecture

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Chain Agent  │    │  Whale Agent │    │ Sentiment    │
│  (RPC Feed)   │───▶│  (Detection) │───▶│ Agent (NLP)  │
└──────┬───────┘    └──────┬───────┘    └──────┬───────┘
       │                   │                   │
       ▼                   ▼                   ▼
┌─────────────────────────────────────────────────────┐
│              Redis Streams (Event Bus)               │
└──────────────────────────┬──────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────┐
│           Inference Pipeline (ROCm GPU)              │
│  ┌─────────┐  ┌──────────┐  ┌───────────────────┐  │
│  │ Tx      │  │ Wallet   │  │ Transformer       │  │
│  │ Encoder │→ │ Embedder │→ │ Classifier (INT8) │  │
│  └─────────┘  └──────────┘  └───────────────────┘  │
└──────────────────────────┬──────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────┐
│              Alert + Dashboard (FastAPI)              │
└─────────────────────────────────────────────────────┘
```

## Components

- **MEV Agent**: Detects sandwich attacks, frontrunning, arbitrage patterns
- **Bridge Agent**: Monitors cross-chain bridge transfers, detects exploits
- **Liquidation Agent**: Tracks DeFi lending liquidations, health factor alerts
- **Chain Agent**: Connects to EVM RPC nodes, streams pending & confirmed blocks, decodes tx calldata
- **Whale Agent**: Classifies wallets by balance/tx patterns, tracks accumulation/distribution cycles
- **Sentiment Agent**: Scrapes CT (Crypto Twitter), runs NLP sentiment model, correlates with on-chain data
- **Exchange Flow Tracker**: CEX deposit/withdrawal pattern analysis
- **Divergence Detector**: Contrarian smart money identification
- **Smart Money Scorer**: ML-based wallet profitability scoring
- **Order Book Depth Analyzer**: DEX liquidity analysis
- **Inference Pipeline**: ROCm-accelerated transformer for wallet classification and tx anomaly detection
- **Alert System**: Telegram/Discord notifications with configurable thresholds

## Supported Chains

- Ethereum (ETH)
- BSC (BNB Smart Chain)
- Arbitrum
- Base
- Polygon

## Quick Start

```bash
# Install
pip install -r requirements.txt

# Configure
cp config/settings.example.yaml config/settings.yaml
# Edit settings.yaml with your RPC endpoints and API keys

# Run agents
python -m src.agents.chain_agent --config config/settings.yaml
python -m src.agents.whale_agent --config config/settings.yaml
python -m src.agents.sentiment_agent --config config/settings.yaml

# Or run all with supervisor
python run_all.py --config config/settings.yaml
```

## ROCm Acceleration

```bash
# Install ROCm
sudo apt install rocm-hip-sdk rocm-libs

# Verify
rocm-smi

# Run with GPU inference
python -m src.models.wallet_classifier --device rocm --model models/wallet-embed-v1.onnx
```

## Smart Money Features

| Feature | Description |
|---------|-------------|
| Whale Tracker | Monitor wallets > $1M balance |
| Smart Money Score | ML-based scoring of wallet profitability |
| Exchange Flow | Track CEX deposit/withdrawal patterns |
| Divergence Detection | Spot wallets buying while market sells |
| Cross-chain Bridge | Monitor bridge tx for large movements |
| VC Tracking | Follow known VC wallet movements |
| Accumulation Alert | Detect steady buying patterns |
| Order Book Depth | DEX liquidity analysis |
| Gini Coefficient | Wealth distribution metrics |
| Heatmap | Visual cluster of whale activity |

## Dashboard

```bash
# Start dashboard
uvicorn src.dashboard.app:app --host 0.0.0.0 --port 8000

# Endpoints
GET /api/health          # Health check
GET /api/whales          # Top whale wallets
GET /api/mev/stats       # MEV detection stats
GET /api/exchange-flow   # CEX flow analysis
GET /api/sentiment       # CT sentiment aggregate
GET /api/liquidation     # Liquidation stats
GET /api/bridge/volume   # Bridge volume stats
WS  /ws/live             # Real-time alert stream
```

## Docker

```bash
cd docker
docker-compose up -d
```

## Project Structure

```
├── src/
│   ├── agents/          # Autonomous agent implementations
│   ├── whale/           # Whale detection & classification
│   ├── sentiment/       # NLP sentiment analysis
│   ├── models/          # ML model inference (ROCm)
│   └── utils/           # Shared utilities
├── config/              # Configuration files
├── scripts/             # Deployment & maintenance scripts
├── tests/               # Unit and integration tests
└── docs/                # Architecture documentation
```

## License

MIT License
