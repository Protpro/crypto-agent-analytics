"""Tests for smart money scorer."""

import pytest
from src.whale.smart_money_score import SmartMoneyScorer


def test_score_empty():
    s = SmartMoneyScorer()
    m = s.score_wallet("0x1234", [])
    assert m.score == 0.0


def test_score_high_winrate():
    s = SmartMoneyScorer()
    trades = [{"pnl": 1000, "entered_before_pump": True, "exit_timing": 0.9}] * 10
    trades += [{"pnl": -100}] * 2
    m = s.score_wallet("0x1234", trades)
    assert m.win_rate > 0.8
    assert m.score > 50


def test_score_low_winrate():
    s = SmartMoneyScorer()
    trades = [{"pnl": -500, "entered_before_pump": False, "exit_timing": 0.1}] * 10
    m = s.score_wallet("0x1234", trades)
    assert m.win_rate == 0.0
    assert m.score < 30
