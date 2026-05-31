"""Tests for divergence detector."""

import pytest
from src.whale.divergence_detector import DivergenceDetector


def test_divergence_buy_in_bearish():
    d = DivergenceDetector()
    d.update_market_trend("bearish")
    tx = {"value_eth": 10, "tags": ["dex:Uniswap"], "chain": "eth"}
    signal = d.analyze_wallet("0x1234", tx)
    assert signal is not None
    assert signal.wallet_action == "buying"
    assert signal.market_trend == "bearish"


def test_no_divergence_buy_in_bullish():
    d = DivergenceDetector()
    d.update_market_trend("bullish")
    tx = {"value_eth": 10, "tags": ["dex:Uniswap"], "chain": "eth"}
    signal = d.analyze_wallet("0x1234", tx)
    assert signal is None


def test_divergence_sell_in_bullish():
    d = DivergenceDetector()
    d.update_market_trend("bullish")
    tx = {"value_eth": 10, "tags": ["cex_deposit:Binance"], "chain": "eth"}
    signal = d.analyze_wallet("0x1234", tx)
    assert signal is not None
    assert signal.wallet_action == "selling"
