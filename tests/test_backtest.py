"""Tests du moteur de backtest sur données synthétiques (sans réseau)."""
import pandas as pd
import pytest

from backtest import Backtester
from cac40_analyzer import build_snapshot, compute_score, prepare_indicators


@pytest.fixture
def backtester(no_fundamentals):
    return Backtester()


# ----------------------- Signal & non-anticipation ----------------------- #

def test_signal_uses_only_previous_sessions_and_executes_at_open(prices, backtester):
    df = prices(days=400)
    backtester.add_price_data("TEST.PA", df)
    date = df.index[300]

    analysis = backtester.analyze_on_date("TEST.PA", date)
    expected = compute_score(build_snapshot(prepare_indicators(df.loc[df.index < date]), {}))

    assert analysis["score"] == expected["score"]
    assert analysis["signal_date"] == df.index[299]
    assert analysis["price"] == df.loc[date, "Open"]


def test_signal_is_unchanged_when_same_day_and_future_data_change(prices, no_fundamentals):
    df = prices(days=400)
    date = df.index[300]
    tampered = df.copy()
    tampered.loc[date:, ["High", "Low", "Close"]] *= 3  # clôture du jour et futur falsifiés

    original, altered = Backtester(), Backtester()
    original.add_price_data("TEST.PA", df)
    altered.add_price_data("TEST.PA", tampered)

    assert original.analyze_on_date("TEST.PA", date)["score"] == altered.analyze_on_date("TEST.PA", date)["score"]


def test_no_analysis_when_the_stock_does_not_trade_that_day(prices, backtester):
    df = prices(days=400)
    backtester.add_price_data("TEST.PA", df.drop(df.index[300]))
    assert backtester.analyze_on_date("TEST.PA", df.index[300]) is None


def test_fundamentals_are_disabled_by_default_in_backtest(prices, backtester, no_fundamentals):
    df = prices(days=400)
    backtester.add_price_data("TEST.PA", df)
    backtester.analyze_on_date("TEST.PA", df.index[300])
    assert no_fundamentals == []


def test_fundamentals_are_fetched_once_per_ticker_when_enabled(prices, backtester, no_fundamentals):
    df = prices(days=400)
    backtester.use_fundamentals = True
    backtester.add_price_data("TEST.PA", df)
    for date in df.index[250:260]:
        backtester.analyze_on_date("TEST.PA", date)
    assert no_fundamentals == ["TEST.PA"]


# ----------------------- Calendrier de rebalance ----------------------- #

def test_rebalance_dates_follow_the_real_trading_calendar(prices, backtester):
    df = prices(days=400, start="2023-01-02")
    df = df.drop(pd.Timestamp("2024-01-01"))  # 1er janvier : bourse fermée
    backtester.add_price_data("TEST.PA", df)

    dates = backtester.rebalance_dates("2024-01-01", "2026-12-31", "month")

    assert dates[0] == pd.Timestamp("2024-01-02")
    assert dates[-1] <= df.index[-1]  # jamais de date postérieure aux données (A2)
    assert all(date in df.index for date in dates)
    assert len({(d.year, d.month) for d in dates}) == len(dates)


@pytest.mark.parametrize("frequency, expected", [("week", 5), ("quarter", 1)])
def test_rebalance_frequencies(prices, backtester, frequency, expected):
    backtester.add_price_data("TEST.PA", prices(days=400, start="2023-01-02"))
    dates = backtester.rebalance_dates("2023-01-02", "2023-02-03", frequency)
    assert len(dates) == expected


def test_unknown_rebalance_frequency_is_rejected(backtester):
    with pytest.raises(ValueError, match="frequency"):
        backtester.rebalance_dates("2024-01-01", "2024-12-31", "daily")
