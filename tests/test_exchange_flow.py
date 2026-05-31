"""Tests for exchange flow tracker."""

import pytest
from src.whale.exchange_flow import ExchangeFlowTracker


def test_deposit_detected():
    tracker = ExchangeFlowTracker()
    tx = {
        "from": "0x1234567890abcdef",
        "to": "0x28c6c06298d514db089934071355e5743bf21d60",  # Binance
        "value_eth": 50,
        "chain": "ethereum",
        "hash": "0xabc",
    }
    event = tracker.process_transaction(tx)
    assert event is not None
    assert event.direction == "deposit"
    assert event.exchange == "Binance"


def test_withdrawal_detected():
    tracker = ExchangeFlowTracker()
    tx = {
        "from": "0x28c6c06298d514db089934071355e5743bf21d60",  # Binance
        "to": "0x1234567890abcdef",
        "value_eth": 100,
        "chain": "ethereum",
        "hash": "0xdef",
    }
    event = tracker.process_transaction(tx)
    assert event is not None
    assert event.direction == "withdrawal"
    assert event.exchange == "Binance"


def test_net_flow():
    tracker = ExchangeFlowTracker()
    # Deposit
    tracker.process_transaction({
        "from": "0x1234", "to": "0x28c6c06298d514db089934071355e5743bf21d60",
        "value_eth": 50, "chain": "eth", "hash": "0x1",
    })
    # Withdrawal
    tracker.process_transaction({
        "from": "0x28c6c06298d514db089934071355e5743bf21d60", "to": "0x5678",
        "value_eth": 30, "chain": "eth", "hash": "0x2",
    })
    net = tracker.get_net_flow("Binance")
    assert net["Binance"]["net"] < 0  # Net outflow
