"""
Exchange Flow — tracks CEX deposit/withdrawal patterns.

Monitors known exchange hot wallets and detects
unusual inflow/outflow patterns that signal market moves.
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field


EXCHANGE_WALLETS = {
    # Binance
    "0x28c6c06298d514db089934071355e5743bf21d60": "Binance",
    "0x21a31ee1afc51d94c2efccaa2092ad1028285549": "Binance",
    "0xdfd5293d8e347dfe59e90efd55b2956a1343963d": "Binance",
    "0x56eddb7aa87536c09ccc2793473599fd21a8b17f": "Binance",
    "0x9696f59e4d72e237be84ffd425dcad154bf96976": "Binance",
    # Coinbase
    "0xa090e606e30bd747d4e6245a1517ebe430f0057e": "Coinbase",
    "0x503828976d22510aad0201ac7ec88293211d23da": "Coinbase",
    "0x71660c4005ba85c37ccec55d0c4493e66fe775d3": "Coinbase",
    "0xa9d1e08c7793af67e9d92fe308d5697fb81d3e43": "Coinbase",
    # Kraken
    "0x2910543af39aba0cd09dbb2d50200b3e800a63d2": "Kraken",
    "0x0a869d79a7052c7f1b55a8ebabbea3420f0d1e13": "Kraken",
    # OKX
    "0x6cc5f688a315f3dc28a7781717a9a798a59fda7b": "OKX",
    "0x236f9f97e0e62388479bf9e5ba4889e46b0273c3": "OKX",
    # Bybit
    "0xf89d7b9c864f589bbf53a82105107622b35eaa40": "Bybit",
}


@dataclass
class ExchangeFlowEvent:
    """Single exchange flow event."""
    exchange: str
    direction: str  # "deposit" or "withdrawal"
    address: str
    amount_eth: float
    amount_usd: float
    chain: str
    tx_hash: str
    timestamp: float = field(default_factory=time.time)


class ExchangeFlowTracker:
    """Tracks exchange inflows and outflows."""

    def __init__(self):
        self.flows: list[ExchangeFlowEvent] = []
        self.inflow: dict[str, float] = defaultdict(float)
        self.outflow: dict[str, float] = defaultdict(float)

    def process_transaction(self, tx: dict) -> ExchangeFlowEvent | None:
        """Process a transaction and detect exchange flows."""
        from_addr = tx.get("from", "").lower()
        to_addr = tx.get("to", "").lower()
        value_eth = tx.get("value_eth", 0)
        value_usd = value_eth * 3000

        # Deposit to exchange
        if to_addr in EXCHANGE_WALLETS:
            event = ExchangeFlowEvent(
                exchange=EXCHANGE_WALLETS[to_addr],
                direction="deposit",
                address=from_addr,
                amount_eth=value_eth,
                amount_usd=value_usd,
                chain=tx.get("chain", "unknown"),
                tx_hash=tx.get("hash", ""),
            )
            self.flows.append(event)
            self.inflow[event.exchange] += value_usd
            return event

        # Withdrawal from exchange
        if from_addr in EXCHANGE_WALLETS:
            event = ExchangeFlowEvent(
                exchange=EXCHANGE_WALLETS[from_addr],
                direction="withdrawal",
                address=to_addr,
                amount_eth=value_eth,
                amount_usd=value_usd,
                chain=tx.get("chain", "unknown"),
                tx_hash=tx.get("hash", ""),
            )
            self.flows.append(event)
            self.outflow[event.exchange] += value_usd
            return event

        return None

    def get_net_flow(self, exchange: str = None) -> dict:
        """Get net flow (positive = net inflow, negative = net outflow)."""
        if exchange:
            return {
                exchange: {
                    "inflow": self.inflow.get(exchange, 0),
                    "outflow": self.outflow.get(exchange, 0),
                    "net": self.inflow.get(exchange, 0) - self.outflow.get(exchange, 0),
                }
            }
        return {
            ex: {
                "inflow": self.inflow.get(ex, 0),
                "outflow": self.outflow.get(ex, 0),
                "net": self.inflow.get(ex, 0) - self.outflow.get(ex, 0),
            }
            for ex in set(list(self.inflow.keys()) + list(self.outflow.keys()))
        }

    def get_summary(self) -> dict:
        """Get exchange flow summary."""
        total_in = sum(self.inflow.values())
        total_out = sum(self.outflow.values())
        return {
            "total_inflow_usd": total_in,
            "total_outflow_usd": total_out,
            "net_flow_usd": total_in - total_out,
            "signal": "bullish" if total_out > total_in * 1.2 else "bearish" if total_in > total_out * 1.2 else "neutral",
            "total_events": len(self.flows),
            "by_exchange": self.get_net_flow(),
        }
