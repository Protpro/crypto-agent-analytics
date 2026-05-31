"""
Liquidation Agent — monitors DeFi lending protocols for liquidation events.

Tracks health factors, predicts liquidations, and alerts on large positions at risk.
"""

import asyncio
import time
from dataclasses import dataclass, field

from src.utils.redis_bus import RedisBus
from src.utils.logger import get_logger

logger = get_logger("liquidation")

LENDING_PROTOCOLS = {
    "0x7d2768de32b0b80b7a3454c06bdac94a69ddc7a9": {"name": "Aave V2", "chain": "ethereum"},
    "0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2": {"name": "Aave V3", "chain": "ethereum"},
    "0x3dfd23a6c5e8bbcfc9581d2e864a68feb6a076d3": {"name": "Aave V2", "chain": "ethereum"},
    "0x4dcf7407ae5c07f8681e1659f626e114a7667339": {"name": "Compound", "chain": "ethereum"},
    "0x39aa39c021dfbae8fac545936693ac917d5e7563": {"name": "Compound", "chain": "ethereum"},
}

# Liquidation call method IDs
LIQUIDATION_METHODS = {
    "0xe8eda72f": "liquidationCall (Aave)",
    "0xf5e3c462": "liquidate (Compound)",
}


@dataclass
class LiquidationEvent:
    """A DeFi liquidation event."""
    protocol: str
    chain: str
    liquidated_user: str
    liquidator: str
    collateral_asset: str
    debt_asset: str
    collateral_amount: float
    debt_amount: float
    tx_hash: str
    block: int
    timestamp: float = field(default_factory=time.time)
    estimated_profit_usd: float = 0.0


@dataclass
class AtRiskPosition:
    """A lending position at risk of liquidation."""
    protocol: str
    user: str
    health_factor: float
    collateral_usd: float
    debt_usd: float
    chain: str
    last_updated: float = field(default_factory=time.time)


class LiquidationAgent:
    """Monitors DeFi liquidations and tracks at-risk positions."""

    def __init__(self, config: dict):
        self.bus = RedisBus(config.get("redis", {}))
        self.config = config.get("liquidation", {})
        self.health_factor_alert = self.config.get("health_factor_alert", 1.1)
        self.liquidations: list[LiquidationEvent] = []
        self.at_risk: dict[str, AtRiskPosition] = {}
        self.total_liquidated_usd = 0.0

    async def run(self, stop: asyncio.Event):
        """Main loop — monitor for liquidation transactions."""
        logger.info("💥 Liquidation Agent started")

        async for event in self.bus.subscribe("chain:transactions"):
            if stop.is_set():
                break
            await self._check_liquidation(event)

    async def _check_liquidation(self, tx: dict):
        """Check if transaction is a liquidation."""
        method_id = tx.get("method_id", "")
        if method_id not in LIQUIDATION_METHODS:
            return

        to_addr = tx.get("to", "").lower()
        protocol_info = LENDING_PROTOCOLS.get(to_addr, {"name": "Unknown", "chain": "unknown"})

        liq_event = LiquidationEvent(
            protocol=protocol_info["name"],
            chain=tx.get("chain", protocol_info["chain"]),
            liquidated_user="unknown",
            liquidator=tx.get("from", ""),
            collateral_asset="unknown",
            debt_asset="unknown",
            collateral_amount=0,
            debt_amount=0,
            tx_hash=tx.get("hash", ""),
            block=tx.get("block", 0),
        )

        self.liquidations.append(liq_event)
        await self._emit_alert(liq_event)

    async def _emit_alert(self, event: LiquidationEvent):
        """Emit liquidation alert."""
        await self.bus.publish("alerts:liquidation", {
            "type": "liquidation",
            "protocol": event.protocol,
            "chain": event.chain,
            "liquidator": event.liquidator,
            "tx_hash": event.tx_hash,
            "block": event.block,
            "timestamp": event.timestamp,
        })
        logger.warning(
            f"💥 Liquidation on {event.protocol} ({event.chain}) | "
            f"by {event.liquidator[:10]}... | tx: {event.tx_hash[:16]}..."
        )

    def get_stats(self) -> dict:
        """Get liquidation statistics."""
        return {
            "total_liquidations": len(self.liquidations),
            "total_liquidated_usd": self.total_liquidated_usd,
            "by_protocol": {
                proto: sum(1 for l in self.liquidations if l.protocol == proto)
                for proto in set(l.protocol for l in self.liquidations)
            },
            "at_risk_count": len(self.at_risk),
        }
