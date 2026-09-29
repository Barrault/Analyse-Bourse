"""Tests du moteur de backtest sur données synthétiques (sans réseau)."""
import pandas as pd
import pytest

from backtest import Backtester, performance_metrics
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


# ----------------------- Exécution des ordres ----------------------- #

def buy_signal(price, confidence=1.0):
    return {"company_name": "Test", "price": price, "confidence": confidence}


def test_buys_a_whole_number_of_shares_within_budget(backtester):
    backtester._execute_buy("SAF.PA", buy_signal(335.10), pd.Timestamp("2024-01-02"))

    trade = backtester.trades[-1]
    assert trade.quantity == 2  # 1000€ max -> 2 x 335,10€ (et non 2,98 actions)
    assert trade.amount == pytest.approx(670.20)
    assert trade.net_cost == pytest.approx(670.20 + 1.90)
    assert trade.net_cost <= 1000
    assert backtester.cash == pytest.approx(backtester.initial_cash - trade.net_cost)


def test_skips_stocks_whose_single_share_exceeds_the_budget(backtester):
    backtester._execute_buy("RMS.PA", buy_signal(2100.0), pd.Timestamp("2024-01-02"))
    assert backtester.trades == []
    assert backtester.cash == backtester.initial_cash


# ----------------------- Règles de sortie ----------------------- #

def neutral_signal(open_price, last_close):
    return {"ticker": "X", "company_name": "X", "date": None, "price": open_price,
            "signal_date": None, "signal_close": last_close,
            "recommendation": "NEUTRE", "confidence": 0.1, "score": 0.0}


@pytest.mark.parametrize("last_close, sold", [(84.0, True), (86.0, False)])
def test_stop_loss_sells_a_neutral_position_after_a_15pct_drop(backtester, last_close, sold):
    backtester._execute_buy("X", buy_signal(100.0), pd.Timestamp("2024-01-02"))
    backtester.analyze_on_date = lambda ticker, date: neutral_signal(83.0, last_close)

    backtester.execute_rebalance(pd.Timestamp("2024-02-01"), ["X"])

    assert ("X" not in backtester.positions) is sold
    if sold:
        assert backtester.trades[-1].recommendation == "STOP-LOSS"
        assert backtester.trades[-1].price == 83.0  # exécuté à l'ouverture


# ----------------------- Simulation complète & métriques ----------------------- #

def test_performance_metrics_on_a_known_curve():
    index = pd.bdate_range("2024-01-01", periods=4)
    metrics = performance_metrics(pd.Series([100.0, 120.0, 90.0, 110.0], index=index))
    assert metrics["total_return_pct"] == pytest.approx(10.0)
    assert metrics["max_drawdown_pct"] == pytest.approx(-25.0)  # 120 -> 90


def test_simulation_values_the_portfolio_every_session_until_the_last_quote(prices, backtester):
    for seed, ticker in enumerate(["A.PA", "B.PA", "C.PA"]):
        backtester.add_price_data(ticker, prices(days=500, seed=seed, drift=0.001))
    backtester.benchmark_data = prices(days=500, seed=99)
    last_quote = backtester.all_data["A.PA"].index[-1]

    backtester.simulate("2023-12-01", "2030-12-31", ["A.PA", "B.PA", "C.PA"])

    sessions = backtester.trading_calendar("2023-12-01", "2030-12-31")
    assert backtester.equity_curve.index[-1] == last_quote
    assert len(backtester.equity_curve) == len(sessions) + 1  # + capital initial la veille
    assert backtester.portfolio_history[-1].date == last_quote
    assert backtester.equity_curve.iloc[-1] == pytest.approx(backtester.portfolio_history[-1].total_value)
    assert len(backtester.benchmark_curve) == len(backtester.equity_curve)
    assert all(trade.date <= last_quote for trade in backtester.trades)
