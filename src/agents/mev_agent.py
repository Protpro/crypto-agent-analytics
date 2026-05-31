"""
MEV Agent — detects MEV activity (sandwich attacks, frontrunning, arbitrage).

Monitors mempool for pending transactions, identifies MEV patterns,
and tracks known MEV searcher wallets.
"""

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field

from src.utils.redis_bus import RedisBus
from src.utils.logger import get_logger

logger = get_logger("mev_agent")

KNOWN_MEV_SEARCHERS = {
    "0x000de2fb0844726e7a2eb5e58656d8f3798857c3": "jaredfromsubway.eth",
    "0x000000000035b5e5ad9019092c665357240f594e": "Titan Builder",
    "0x000069c417c60508f475842e5eb756063612c925": "Flashbots Builder",
    "0x4838b106fce9647bdf1e78771e20f3a1821f9565": "beaver.build",
    "0xb64a30399f4f68c0bed82e172a4de28505a5c4a8": "rsync-builder",
}


@dataclass
class MEVPattern:
    """Detected MEV pattern."""
    pattern_type: str  # sandwich, frontrun, backrun, arbitrage, liquidation
    chain: str
    block: int
    attacker: str
    victim: str
    profit_eth: float
    profit_usd: float
    tx_hash: str
    timestamp: float = field(default_factory=time.time)
    details: dict = field(default_factory=dict)


class MEVAgent:
    """Detects and tracks MEV activity across chains."""

    def __init__(self, config: dict):
        self.bus = RedisBus(config.get("redis", {}))
        self.config = config.get("mev", {})
        self.min_profit_eth = self.config.get("min_profit_eth", 0.01)
        self.detected: list[MEVPattern] = []
        self.searcher_stats: dict[str, dict] = defaultdict(lambda: {
            "count": 0, "total_profit": 0.0, "patterns": defaultdict(int)
        })

    async def run(self, stop: asyncio.Event):
        """Main loop — process transactions for MEV patterns."""
        logger.info("🔍 MEV Agent started")

        async for event in self.bus.subscribe("chain:transactions"):
            if stop.is_set():
                break
            await self._analyze_transaction(event)

    async def _analyze_transaction(self, tx: dict):
        """Analyze transaction for MEV patterns."""
        to_addr = tx.get("to", "").lower()

        # Check known MEV searchers
        if to_addr in KNOWN_MEV_SEARCHERS:
            searcher_name = KNOWN_MEV_SEARCHERS[to_addr]
            self.searcher_stats[to_addr]["count"] += 1
            logger.debug(f"Known MEV searcher: {searcher_name}")

        # Detect sandwich pattern
        pattern = self._detect_sandwich(tx)
        if pattern:
            await self._emit_pattern(pattern)

        # Detect frontrunning
        pattern = self._detect_frontrun(tx)
        if pattern:
            await self._emit_pattern(pattern)

    def _detect_sandwich(self, tx: dict) -> MEVPattern | None:
        """Detect sandwich attack pattern."""
        tags = tx.get("tags", [])
        has_dex = any("dex" in str(t) for t in tags)

        if not has_dex:
            return None

        # Simplified: check if tx interacts with known sandwich contracts
        to_addr = tx.get("to", "").lower()
        if to_addr in KNOWN_MEV_SEARCHERS:
            value = tx.get("value_eth", 0)
            if value > self.min_profit_eth:
                return MEVPattern(
                    pattern_type="sandwich",
                    chain=tx.get("chain", "unknown"),
                    block=tx.get("block", 0),
                    attacker=to_addr,
                    victim=tx.get("from", ""),
                    profit_eth=value * 0.01,  # Estimated
                    profit_usd=value * 0.01 * 3000,  # Rough ETH price
                    tx_hash=tx.get("hash", ""),
                )
        return None

    def _detect_frontrun(self, tx: dict) -> MEVPattern | None:
        """Detect frontrunning pattern."""
        gas_price = tx.get("gas_price_gwei", 0)
        if gas_price > 500:  # Abnormally high gas = potential frontrun
            tags = tx.get("tags", [])
            if any("dex" in str(t) for t in tags):
                return MEVPattern(
                    pattern_type="frontrun",
                    chain=tx.get("chain", "unknown"),
                    block=tx.get("block", 0),
                    attacker=tx.get("from", ""),
                    victim="unknown",
                    profit_eth=0,
                    profit_usd=0,
                    tx_hash=tx.get("hash", ""),
                    details={"gas_price_gwei": gas_price},
                )
        return None

    async def _emit_pattern(self, pattern: MEVPattern):
        """Emit detected MEV pattern to event bus."""
        self.detected.append(pattern)
        await self.bus.publish("alerts:mev", {
            "type": f"mev_{pattern.pattern_type}",
            "chain": pattern.chain,
            "attacker": pattern.attacker,
            "victim": pattern.victim,
            "profit_eth": pattern.profit_eth,
            "profit_usd": pattern.profit_usd,
            "tx_hash": pattern.tx_hash,
            "timestamp": pattern.timestamp,
        })
        logger.warning(
            f"🚨 MEV {pattern.pattern_type}: {pattern.attacker[:10]}... "
            f"profit {pattern.profit_eth:.4f} ETH (${pattern.profit_usd:.2f})"
        )

    def get_stats(self) -> dict:
        """Get MEV detection statistics."""
        return {
            "total_detected": len(self.detected),
            "by_type": defaultdict(int, {
                p.pattern_type: sum(1 for d in self.detected if d.pattern_type == p.pattern_type)
                for p in self.detected
            }),
            "top_searchers": sorted(
                [{"address": k, **v} for k, v in self.searcher_stats.items()],
                key=lambda x: x["count"], reverse=True
            )[:10],
        }
