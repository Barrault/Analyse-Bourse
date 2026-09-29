"""Tests du moteur de backtest sur données synthétiques (sans réseau)."""
import pandas as pd

from backtest import Backtester
from cac40_analyzer import build_snapshot, compute_score, prepare_indicators


def test_precomputed_indicators_match_a_computation_on_truncated_history(prices, no_fundamentals):
    df = prices(days=400)
    backtester = Backtester()
    backtester.add_price_data("TEST.PA", df)
    date = df.index[300]

    precomputed = backtester.analyze_on_date("TEST.PA", date)
    truncated = compute_score(build_snapshot(prepare_indicators(df.loc[:date]), {}))

    assert precomputed["score"] == truncated["score"]
    assert precomputed["price"] == df.loc[date, "Close"]


def test_fundamentals_are_fetched_once_per_ticker(prices, no_fundamentals):
    df = prices(days=400)
    backtester = Backtester()
    backtester.add_price_data("TEST.PA", df)
    for date in df.index[250:260]:
        backtester.analyze_on_date("TEST.PA", date)
    assert no_fundamentals == ["TEST.PA"]
