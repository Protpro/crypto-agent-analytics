"""
Smart Money Score — ML-based wallet profitability scoring.

Scores wallets based on historical trade timing, win rate,
and correlation with known profitable wallets.
"""

import numpy as np
from dataclasses import dataclass, field


@dataclass
class SmartMoneyMetrics:
    """Metrics for smart money scoring."""
    win_rate: float = 0.0
    avg_hold_time_hours: float = 0.0
    total_trades: int = 0
    total_pnl_usd: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    early_entry_rate: float = 0.0  # % of trades entered before 10% move
    exit_timing_score: float = 0.0  # How close to local top/bottom
    score: float = 0.0


class SmartMoneyScorer:
    """Scores wallets based on trading performance."""

    # Weights for composite score
    WEIGHTS = {
        "win_rate": 0.25,
        "sharpe_ratio": 0.20,
        "early_entry_rate": 0.15,
        "exit_timing_score": 0.15,
        "pnl_normalized": 0.15,
        "consistency": 0.10,
    }

    def __init__(self):
        self.scores: dict[str, SmartMoneyMetrics] = {}

    def score_wallet(self, address: str, trades: list[dict]) -> SmartMoneyMetrics:
        """Calculate smart money score for a wallet."""
        if not trades:
            return SmartMoneyMetrics()

        metrics = SmartMoneyMetrics()
        metrics.total_trades = len(trades)

        # Win rate
        wins = sum(1 for t in trades if t.get("pnl", 0) > 0)
        metrics.win_rate = wins / metrics.total_trades

        # Total PnL
        pnls = [t.get("pnl", 0) for t in trades]
        metrics.total_pnl_usd = sum(pnls)

        # Sharpe ratio
        if len(pnls) > 1:
            mean_pnl = np.mean(pnls)
            std_pnl = np.std(pnls)
            metrics.sharpe_ratio = mean_pnl / std_pnl if std_pnl > 0 else 0

        # Max drawdown
        cumulative = np.cumsum(pnls)
        peak = np.maximum.accumulate(cumulative)
        drawdown = (peak - cumulative) / (peak + 1e-8)
        metrics.max_drawdown = float(np.max(drawdown))

        # Early entry rate
        early_entries = sum(1 for t in trades if t.get("entered_before_pump", False))
        metrics.early_entry_rate = early_entries / metrics.total_trades

        # Exit timing
        exit_scores = [t.get("exit_timing", 0.5) for t in trades]
        metrics.exit_timing_score = np.mean(exit_scores)

        # Composite score
        metrics.score = self._compute_composite(metrics)

        self.scores[address] = metrics
        return metrics

    def _compute_composite(self, m: SmartMoneyMetrics) -> float:
        """Compute weighted composite score (0-100)."""
        pnl_norm = min(max(m.total_pnl_usd / 1_000_000, 0), 1)  # Cap at $1M
        consistency = 1 - m.max_drawdown

        score = (
            self.WEIGHTS["win_rate"] * m.win_rate +
            self.WEIGHTS["sharpe_ratio"] * min(max(m.sharpe_ratio / 3, 0), 1) +
            self.WEIGHTS["early_entry_rate"] * m.early_entry_rate +
            self.WEIGHTS["exit_timing_score"] * m.exit_timing_score +
            self.WEIGHTS["pnl_normalized"] * pnl_norm +
            self.WEIGHTS["consistency"] * consistency
        )

        return round(score * 100, 2)

    def get_top_smart_money(self, n: int = 20) -> list:
        """Get top N smart money wallets."""
        return sorted(
            [{"address": k, **v.__dict__} for k, v in self.scores.items()],
            key=lambda x: x["score"],
            reverse=True
        )[:n]
