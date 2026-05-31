"""
FastAPI Dashboard — real-time analytics dashboard.

REST API endpoints for whale data, MEV stats, exchange flows,
sentiment, and liquidation monitoring.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
import time

app = FastAPI(title="Crypto Agent Analytics", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared state (injected by supervisor)
agents = {}
ws_clients: list[WebSocket] = []


@app.get("/api/health")
async def health():
    return {"status": "ok", "timestamp": time.time()}


@app.get("/api/whales")
async def get_whales(limit: int = 20):
    whale_agent = agents.get("whale")
    if not whale_agent:
        return {"error": "whale agent not running"}
    whales = whale_agent.get_top_whales(limit)
    return {"whales": [w.to_dict() if hasattr(w, "to_dict") else w for w in whales]}


@app.get("/api/mev/stats")
async def get_mev_stats():
    mev_agent = agents.get("mev")
    if not mev_agent:
        return {"error": "mev agent not running"}
    return mev_agent.get_stats()


@app.get("/api/exchange-flow")
async def get_exchange_flow():
    # Placeholder — returns from shared state
    return {"flows": [], "net_flow": {}}


@app.get("/api/sentiment")
async def get_sentiment():
    sentiment_agent = agents.get("sentiment")
    if not sentiment_agent:
        return {"error": "sentiment agent not running"}
    return sentiment_agent.get_aggregate_sentiment()


@app.get("/api/liquidation/stats")
async def get_liquidation_stats():
    liq_agent = agents.get("liquidation")
    if not liq_agent:
        return {"error": "liquidation agent not running"}
    return liq_agent.get_stats()


@app.get("/api/bridge/volume")
async def get_bridge_volume():
    bridge_agent = agents.get("bridge")
    if not bridge_agent:
        return {"error": "bridge agent not running"}
    return bridge_agent.get_volume_stats()


@app.websocket("/ws/live")
async def websocket_live(ws: WebSocket):
    """WebSocket endpoint for real-time alerts."""
    await ws.accept()
    ws_clients.append(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        ws_clients.remove(ws)


async def broadcast_alert(alert: dict):
    """Broadcast alert to all WebSocket clients."""
    for ws in ws_clients[:]:
        try:
            await ws.send_json(alert)
        except Exception:
            ws_clients.remove(ws)


def set_agents(agent_dict: dict):
    """Inject agent references for dashboard queries."""
    global agents
    agents = agent_dict
