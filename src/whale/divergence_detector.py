"""
Divergence Detector — spots wallets buying while market sells.

Identifies contrarian smart money that accumulates during
market downturns and distributes during euphoria.
"""

import time
from dataclasses import dataclass, field


@dataclass
class DivergenceSignal:
    """A divergence signal — wallet acting against market trend."""
    wallet: str
    market_trend: str  # "bullish" or "bearish"
    wallet_action: str  # "buying" or "selling"
    divergence_strength: float  # 0-1
    amount_usd: float
    asset: str
    chain: str
    timestamp: float = field(default_factory=time.time)
    details: dict = field(default_factory=dict)


class DivergenceDetector:
    """Detects divergence between wallet behavior and market trend."""

    def __init__(self):
        self.signals: list[DivergenceSignal] = []
        self.market_trend = "neutral"
        self.wallet_actions: dict[str, list] = {}

    def update_market_trend(self, trend: str):
        """Update current market trend from sentiment agent."""
        self.market_trend = trend

    def analyze_wallet(self, wallet: str, tx: dict) -> DivergenceSignal | None:
        """Analyze a wallet transaction against market trend."""
        if self.market_trend == "neutral":
            return None

        value_usd = tx.get("value_eth", 0) * 3000
        tags = tx.get("tags", [])

        # Determine wallet action
        action = None
        if any("cex_deposit" in str(t) for t in tags):
            action = "selling"  # Depositing to CEX = selling
        elif any("dex" in str(t) for t in tags):
            action = "buying"  # Buying on DEX = accumulating

        if not action:
            return None

        # Track actions
        if wallet not in self.wallet_actions:
            self.wallet_actions[wallet] = []
        self.wallet_actions[wallet].append({"action": action, "value_usd": value_usd, "time": time.time()})

        # Check for divergence
        is_divergence = (
            (self.market_trend == "bearish" and action == "buying") or
            (self.market_trend == "bullish" and action == "selling")
        )

        if not is_divergence:
            return None

        # Calculate divergence strength
        recent = self.wallet_actions[wallet][-10:]
        same_action_count = sum(1 for r in recent if r["action"] == action)
        strength = same_action_count / len(recent)

        signal = DivergenceSignal(
            wallet=wallet,
            market_trend=self.market_trend,
            wallet_action=action,
            divergence_strength=strength,
            amount_usd=value_usd,
            asset="ETH",
            chain=tx.get("chain", "unknown"),
        )

        self.signals.append(signal)
        return signal

    def get_strongest_signals(self, n: int = 10) -> list:
        """Get the strongest divergence signals."""
        return sorted(self.signals, key=lambda s: s.divergence_strength, reverse=True)[:n]
