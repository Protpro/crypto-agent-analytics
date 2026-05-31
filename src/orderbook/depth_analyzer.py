"""
Order Book Depth Analyzer — DEX liquidity analysis.

Analyzes Uniswap V3 concentrated liquidity positions,
calculates effective spread, and detects liquidity imbalances.
"""

import time
from dataclasses import dataclass, field


@dataclass
class LiquidityPosition:
    """A concentrated liquidity position (Uniswap V3 style)."""
    pool: str
    owner: str
    lower_tick: int
    upper_tick: int
    liquidity: float
    chain: str
    token0: str = ""
    token1: str = ""
    value_usd: float = 0.0


@dataclass
class DepthSnapshot:
    """Order book depth snapshot at a point in time."""
    pool: str
    chain: str
    bid_depth_usd: float
    ask_depth_usd: float
    spread_bps: float
    imbalance: float  # -1 (all asks) to +1 (all bids)
    liquidity_score: float  # 0-1
    timestamp: float = field(default_factory=time.time)


class DepthAnalyzer:
    """Analyzes DEX order book depth and liquidity."""

    def __init__(self):
        self.positions: dict[str, list[LiquidityPosition]] = {}
        self.snapshots: list[DepthSnapshot] = []

    def add_position(self, position: LiquidityPosition):
        """Add or update a liquidity position."""
        pool = position.pool
        if pool not in self.positions:
            self.positions[pool] = []
        self.positions[pool].append(position)

    def calculate_depth(self, pool: str, current_tick: int, chain: str) -> DepthSnapshot:
        """Calculate bid/ask depth for a pool."""
        positions = self.positions.get(pool, [])

        bid_depth = 0.0
        ask_depth = 0.0

        for pos in positions:
            if pos.upper_tick <= current_tick:
                bid_depth += pos.value_usd
            elif pos.lower_tick >= current_tick:
                ask_depth += pos.value_usd
            else:
                # Position straddles current tick
                bid_ratio = (current_tick - pos.lower_tick) / (pos.upper_tick - pos.lower_tick)
                bid_depth += pos.value_usd * bid_ratio
                ask_depth += pos.value_usd * (1 - bid_ratio)

        total = bid_depth + ask_depth
        imbalance = (bid_depth - ask_depth) / total if total > 0 else 0

        snapshot = DepthSnapshot(
            pool=pool,
            chain=chain,
            bid_depth_usd=bid_depth,
            ask_depth_usd=ask_depth,
            spread_bps=abs(imbalance) * 100,
            imbalance=imbalance,
            liquidity_score=min(total / 1_000_000, 1.0),  # Normalized
        )

        self.snapshots.append(snapshot)
        return snapshot

    def detect_liquidity_drain(self, pool: str, window_seconds: int = 3600) -> dict:
        """Detect if liquidity is being drained from a pool."""
        recent = [
            s for s in self.snapshots
            if s.pool == pool and time.time() - s.timestamp < window_seconds
        ]

        if len(recent) < 2:
            return {"draining": False, "change_pct": 0}

        first_depth = recent[0].bid_depth_usd + recent[0].ask_depth_usd
        last_depth = recent[-1].bid_depth_usd + recent[-1].ask_depth_usd

        change_pct = ((last_depth - first_depth) / first_depth * 100) if first_depth > 0 else 0

        return {
            "draining": change_pct < -20,  # 20%+ drop
            "change_pct": round(change_pct, 2),
            "first_depth_usd": first_depth,
            "last_depth_usd": last_depth,
        }
