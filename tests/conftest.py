"""Fixtures partagées."""
import numpy as np
import pandas as pd
import pytest

from cac40_analyzer import IndicatorSnapshot


def make_snapshot(pe=None, pb=None, dy=None, eps=None, bullish=True):
    """Instantané aux indicateurs techniques haussiers (ou baissiers) et fondamentaux donnés."""
    if bullish:
        technicals = dict(close=100.0, sma20=100.0, sma50=100.0, sma200=95.0, rsi14=55.0,
                          macd=1.0, macd_hist=0.5, bb_lower=95.0)
    else:
        technicals = dict(close=80.0, sma20=85.0, sma50=90.0, sma200=100.0, rsi14=40.0,
                          macd=-1.0, macd_hist=-0.5, bb_lower=75.0)
    return IndicatorSnapshot(
        date=pd.Timestamp("2024-01-01"),
        macd_signal=0.0,
        bb_mid=100.0,
        bb_upper=105.0,
        atr14=2.0,
        vol=1_000_000.0,
        vol_sma20=900_000.0,
        fundamentals={"trailingPE": pe, "priceToBook": pb, "dividendYield": dy, "trailingEps": eps},
        **technicals,
    )


@pytest.fixture
def snapshot():
    """Fabrique d'IndicatorSnapshot : snapshot(pe=..., pb=..., dy=..., eps=..., bullish=...)."""
    return make_snapshot


def make_prices(days=400, start="2023-01-02", seed=0, drift=0.0005):
    """Historique OHLCV synthétique sur jours ouvrés, sans appel réseau."""
    rng = np.random.default_rng(seed)
    index = pd.bdate_range(start, periods=days)
    close = 100 * np.exp(np.cumsum(rng.normal(drift, 0.01, days)))
    open_ = close * (1 + rng.normal(0, 0.003, days))
    return pd.DataFrame({
        "Open": open_,
        "High": np.maximum(open_, close) * 1.01,
        "Low": np.minimum(open_, close) * 0.99,
        "Close": close,
        "Volume": rng.integers(1_000, 10_000, days).astype(float),
    }, index=index)


@pytest.fixture
def prices():
    """Fabrique d'historiques synthétiques : prices(days=..., seed=..., drift=...)."""
    return make_prices


@pytest.fixture
def no_fundamentals(monkeypatch):
    """Neutralise les appels Yahoo des fondamentaux et compte les appels."""
    import backtest
    calls = []

    def fake(ticker):
        calls.append(ticker)
        return {}
    monkeypatch.setattr(backtest, "fetch_fundamentals_safe", fake)
    return calls
