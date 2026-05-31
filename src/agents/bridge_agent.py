"""
Bridge Agent — monitors cross-chain bridge transactions.

Tracks large bridge transfers, detects bridge exploits,
and monitors liquidity across bridge protocols.
"""

import asyncio
import time
from dataclasses import dataclass, field

from src.utils.redis_bus import RedisBus
from src.utils.logger import get_logger

logger = get_logger("bridge_agent")

BRIDGE_CONTRACTS = {
    "0x3154cf16ccdb4c6d922629664174b904d80f2c35": {"name": "Across", "chain": "ethereum"},
    "0x99c9fc46f92e8a1c0dec1b1747d010903e884be1": {"name": "Optimism Bridge", "chain": "ethereum"},
    "0x4dbd4fc535ac27206064b68ffcf827b0a60bab3f": {"name": "Arbitrum Inbox", "chain": "ethereum"},
    "0x40ec5b33f54e0e8a33a975908c5ba1c14e5bbbdf": {"name": "Polygon Bridge", "chain": "ethereum"},
    "0x5e4a41b1329358081ff1a44d42406d5c4b6e34b1": {"name": "Stargate", "chain": "ethereum"},
    "0xdf0770df86a8034b3efef0a1ff3118c0647195f2": {"name": "Stargate", "chain": "bsc"},
    "0xe3ec7338594843175105337ab4d10c4f20e04d12": {"name": "Synapse", "chain": "ethereum"},
}

# Thresholds
LARGE_BRIDGE_ETH = 100
LARGE_BRIDGE_USD = 500_000


@dataclass
class BridgeEvent:
    """Cross-chain bridge transaction."""
    bridge: str
    source_chain: str
    dest_chain: str
    sender: str
    amount_eth: float
    amount_usd: float
    tx_hash: str
    timestamp: float = field(default_factory=time.time)
    flagged: bool = False
    flag_reason: str = ""


class BridgeAgent:
    """Monitors bridge transactions for large movements and anomalies."""

    def __init__(self, config: dict):
        self.bus = RedisBus(config.get("redis", {}))
        self.config = config.get("bridge", {})
        self.min_alert_usd = self.config.get("min_alert_usd", 500_000)
        self.events: list[BridgeEvent] = []
        self.bridge_volume: dict[str, float] = {}

    async def run(self, stop: asyncio.Event):
        """Main loop — monitor bridge transactions."""
        logger.info("🌉 Bridge Agent started")

        async for event in self.bus.subscribe("chain:transactions"):
            if stop.is_set():
                break
            await self._check_bridge(event)

    async def _check_bridge(self, tx: dict):
        """Check if transaction interacts with bridge contracts."""
        to_addr = tx.get("to", "").lower()
        if to_addr not in BRIDGE_CONTRACTS:
            return

        bridge_info = BRIDGE_CONTRACTS[to_addr]
        value_eth = tx.get("value_eth", 0)
        value_usd = value_eth * 3000  # Rough estimate

        bridge_event = BridgeEvent(
            bridge=bridge_info["name"],
            source_chain=tx.get("chain", bridge_info["chain"]),
            dest_chain="unknown",
            sender=tx.get("from", ""),
            amount_eth=value_eth,
            amount_usd=value_usd,
            tx_hash=tx.get("hash", ""),
        )

        # Flag large transfers
        if value_eth > LARGE_BRIDGE_ETH:
            bridge_event.flagged = True
            bridge_event.flag_reason = f"Large bridge transfer: {value_eth:.2f} ETH"

        self.events.append(bridge_event)

        # Track volume per bridge
        bridge_name = bridge_info["name"]
        self.bridge_volume[bridge_name] = self.bridge_volume.get(bridge_name, 0) + value_usd

        if bridge_event.flagged:
            await self._emit_alert(bridge_event)

    async def _emit_alert(self, event: BridgeEvent):
        """Emit bridge alert."""
        await self.bus.publish("alerts:bridge", {
            "type": "large_bridge_transfer",
            "bridge": event.bridge,
            "source_chain": event.source_chain,
            "sender": event.sender,
            "amount_eth": event.amount_eth,
            "amount_usd": event.amount_usd,
            "tx_hash": event.tx_hash,
            "reason": event.flag_reason,
            "timestamp": event.timestamp,
        })
        logger.warning(
            f"🌉 Bridge alert: {event.bridge} | "
            f"{event.amount_eth:.2f} ETH (${event.amount_usd:,.0f}) | "
            f"{event.sender[:10]}..."
        )

    def get_volume_stats(self) -> dict:
        """Get bridge volume statistics."""
        return {
            "total_events": len(self.events),
            "total_volume_usd": sum(e.amount_usd for e in self.events),
            "by_bridge": dict(self.bridge_volume),
            "flagged_count": sum(1 for e in self.events if e.flagged),
        }
