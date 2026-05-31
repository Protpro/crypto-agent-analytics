"""Tests for whale agent."""

import pytest
from src.agents.whale_agent import WalletProfile, WhaleAgent


def test_wallet_profile_init():
    p = WalletProfile("0x1234")
    assert p.address == "0x1234"
    assert p.tx_count == 0
    assert p.behavior == "unknown"


def test_wallet_profile_update():
    p = WalletProfile("0x1234")
    p.update({"chain": "ethereum", "tags": ["dex:Uniswap"]})
    assert p.tx_count == 1
    assert "ethereum" in p.chains


def test_wallet_is_whale():
    p = WalletProfile("0x1234")
    p.total_volume_usd = 2_000_000
    assert p.is_whale


def test_wallet_not_whale():
    p = WalletProfile("0x1234")
    p.total_volume_usd = 500_000
    assert not p.is_whale


def test_win_rate():
    p = WalletProfile("0x1234")
    p.win_count = 7
    p.loss_count = 3
    assert abs(p.win_rate - 0.7) < 0.001


def test_wallet_to_dict():
    p = WalletProfile("0x1234")
    d = p.to_dict()
    assert "address" in d
    assert "smart_money_score" in d
