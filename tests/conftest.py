"""Fixtures partagées."""
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
