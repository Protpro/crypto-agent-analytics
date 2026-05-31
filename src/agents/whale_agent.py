"""
Whale Agent — monitors large wallets and detects smart money patterns.

Subscribes to chain events, enriches with wallet data,
and scores wallets based on historical profitability.
"""

import asyncio
import json
import time
from collections import defaultdict
from typing import Optional

from src.utils.redis_bus import RedisBus
from src.utils.logger import get_logger

logger = get_logger("whale_agent")


class WalletProfile:
    """Wallet behavior profile with rolling metrics."""

    def __init__(self, address: str):
        self.address = address
        self.first_seen = time.time()
        self.last_active = time.time()
        self.tx_count = 0
        self.total_volume_usd = 0.0
        self.profit_loss = 0.0
        self.win_count = 0
        self.loss_count = 0
        self.tags = set()
        self.chains = set()
        self.smart_money_score = 0.0
        self.behavior = "unknown"

    def update(self, tx: dict):
        self.last_active = time.time()
        self.tx_count += 1
        self.chains.add(tx.get("chain", "unknown"))
        for tag in tx.get("tags", []):
            self.tags.add(tag)

    @property
    def win_rate(self) -> float:
        total = self.win_count + self.loss_count
        return self.win_count / total if total > 0 else 0.0

    @property
    def is_whale(self) -> bool:
        return self.total_volume_usd > 1_000_000

    def to_dict(self) -> dict:
        return {
            "address": self.address,
            "tx_count": self.tx_count,
            "volume_usd": self.total_volume_usd,
            "smart_money_score": self.smart_money_score,
            "win_rate": self.win_rate,
            "behavior": self.behavior,
            "chains": list(self.chains),
            "tags": list(self.tags),
        }


class WhaleAgent:
    """Tracks whale wallets and detects accumulation/distribution."""

    def __init__(self, config: dict):
        self.bus = RedisBus(config.get("redis", {}))
        self.wallets: dict[str, WalletProfile] = {}
        self.whale_threshold = config.get("whale", {}).get("min_value_usd", 1_000_000)
        self.alert_callbacks = []

    async def run(self, stop: asyncio.Event):
        """Subscribe to chain events and process whale transactions."""
        logger.info("🐋 Whale Agent started")

        async for event in self.bus.subscribe("chain:transactions"):
            if stop.is_set():
                break
            await self._process_event(event)

    async def _process_event(self, event: dict):
        """Process a transaction event."""
        for addr in [event.get("from"), event.get("to")]:
            if not addr:
                continue

            if addr not in self.wallets:
                self.wallets[addr] = WalletProfile(addr)

            profile = self.wallets[addr]
            profile.update(event)

            # Check if whale
            if profile.is_whale:
                await self._analyze_whale(profile, event)

    async def _analyze_whale(self, profile: WalletProfile, tx: dict):
        """Analyze whale behavior patterns."""
        old_behavior = profile.behavior

        # Simple accumulation/distribution detection
        if "cex_deposit" in str(tx.get("tags", [])):
            profile.behavior = "distributing"
        elif "dex" in str(tx.get("tags", [])):
            if tx.get("value_eth", 0) > 50:
                profile.behavior = "accumulating"

        if profile.behavior != old_behavior:
            await self._emit_alert(profile, old_behavior)

    async def _emit_alert(self, profile: WalletProfile, old_behavior: str):
        """Emit whale behavior change alert."""
        alert = {
            "type": "whale_behavior_change",
            "address": profile.address,
            "old_behavior": old_behavior,
            "new_behavior": profile.behavior,
            "smart_money_score": profile.smart_money_score,
            "volume_usd": profile.total_volume_usd,
            "timestamp": time.time(),
        }
        await self.bus.publish("alerts:whale", alert)
        logger.warning(
            f"🐋 Whale alert: {profile.address[:10]}... "
            f"{old_behavior} → {profile.behavior} "
            f"(score: {profile.smart_money_score:.2f})"
        )

    def get_top_whales(self, n: int = 20) -> list:
        """Get top N whales by volume."""
        return sorted(
            self.wallets.values(),
            key=lambda w: w.total_volume_usd,
            reverse=True
        )[:n]
