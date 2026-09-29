"""Tests de la récupération des fondamentaux (Yahoo simulé)."""
import pytest

import cac40_analyzer


class FakeTicker:
    def __init__(self, info):
        self.info = info


@pytest.fixture
def fake_info(monkeypatch):
    def install(info):
        monkeypatch.setattr(cac40_analyzer.yf, "Ticker", lambda _ticker: FakeTicker(info))
    return install


def test_dividend_yield_is_already_a_percentage(fake_info):
    # yfinance >= 0.2.54 : 0.68 signifie 0,68 %, et non 68 % (constat A1)
    fake_info({"trailingPE": 20.0, "priceToBook": 2.0, "dividendYield": 0.68})
    assert cac40_analyzer.fetch_fundamentals_safe("STMPA.PA")["dividendYield"] == pytest.approx(0.68)


def test_fundamentals_are_none_when_yahoo_fails(monkeypatch):
    def boom(_ticker):
        raise ConnectionError("rate limited")
    monkeypatch.setattr(cac40_analyzer.yf, "Ticker", boom)
    fundamentals = cac40_analyzer.fetch_fundamentals_safe("AC.PA")
    assert all(value is None for value in fundamentals.values())
