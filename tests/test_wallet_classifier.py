"""Tests for wallet classifier."""

import pytest
from src.models.wallet_classifier import WalletClassifier


def test_classify_empty():
    c = WalletClassifier.__new__(WalletClassifier)
    c.session = None
    result = c.classify([])
    assert result["label"] == "unknown"


def test_classify_whale_heuristic():
    c = WalletClassifier.__new__(WalletClassifier)
    c.session = None
    txs = [{"value_eth": 5000, "tags": []} for _ in range(10)]
    result = c.classify(txs)
    assert result["label"] == "whale"


def test_classify_bot_heuristic():
    c = WalletClassifier.__new__(WalletClassifier)
    c.session = None
    txs = [{"value_eth": 1, "tags": ["dex:Uniswap"]} for _ in range(150)]
    result = c.classify(txs)
    assert result["label"] == "bot"


def test_encode_transaction():
    c = WalletClassifier.__new__(WalletClassifier)
    c.session = None
    tx = {"value_eth": 10, "gas_price_gwei": 30, "tags": ["dex"], "chain": "eth"}
    vec = c.encode_transaction(tx)
    assert len(vec) == 6
