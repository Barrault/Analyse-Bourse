"""Tests des outils statistiques de calibrage."""
import numpy as np
import pandas as pd
import pytest

from backtest import Backtester
from calibrate import (calibration_table, forward_excess_return, isotonic_increasing,
                       keep_component, monthly_spread)


def test_isotonic_regression_pools_violations_with_weights():
    assert isotonic_increasing([0.4, 0.6, 0.5, 0.7], [1, 1, 1, 1]) == pytest.approx([0.4, 0.55, 0.55, 0.7])
    assert isotonic_increasing([0.6, 0.3], [3, 1]) == pytest.approx([0.525, 0.525])
    assert isotonic_increasing([0.1, 0.2, 0.3], [1, 1, 1]) == [0.1, 0.2, 0.3]


def test_keep_component_rule():
    assert keep_component(+3.0, 2.5, +1, min_t=1.0)
    assert not keep_component(+3.0, 0.5, +1, min_t=1.0)   # effet non significatif
    assert not keep_component(+3.0, 2.5, -1, min_t=1.0)   # signe contraire : mis à 0, jamais inversé


def test_monthly_spread_measures_the_gap_between_groups():
    dates = np.repeat(pd.date_range("2020-01-01", periods=6, freq="MS"), 10)
    rng = np.random.default_rng(0)
    df = pd.DataFrame({"date": dates, "flag": np.tile([True] * 5 + [False] * 5, 6)})
    df["rank"] = np.where(df.flag, 60, 40) + rng.normal(0, 1, len(df))
    spread, t_stat, months = monthly_spread(df, df["flag"])
    assert spread == pytest.approx(20, abs=1) and t_stat > 10 and months == 6


def test_calibration_table_is_monotonic_in_score():
    rng = np.random.default_rng(1)
    scores = rng.normal(0, 3, 2000)
    excess = scores * 0.5 + rng.normal(0, 5, 2000)
    table = calibration_table(pd.DataFrame({"technical_score": scores, "excess": excess}), n_bins=5)
    assert len(table["probabilities"]) == len(table["score_edges"]) + 1 == 5
    assert table["probabilities"] == sorted(table["probabilities"])
    assert table["probabilities"][-1] > 0.5 > table["probabilities"][0]


def test_forward_excess_return_is_measured_against_the_benchmark(prices, no_fundamentals):
    backtester = Backtester()
    stock = prices(days=300, seed=1)
    backtester.add_price_data("A.PA", stock)
    backtester.benchmark_data = stock.copy()  # benchmark identique au titre
    date = stock.index[100]
    assert forward_excess_return(backtester, "A.PA", date, stock.loc[date, "Open"], 63) == pytest.approx(0)
    assert np.isnan(forward_excess_return(backtester, "A.PA", stock.index[-10], 1.0, 63))


def test_dividend_yield_is_trailing_12_months_over_raw_price(monkeypatch):
    import calibrate
    index = pd.date_range("2024-01-01", periods=400, freq="D", tz="Europe/Paris")
    history = pd.DataFrame({"Close": 50.0, "Dividends": 0.0}, index=index)
    history.loc[index[10], "Dividends"] = 1.0
    history.loc[index[200], "Dividends"] = 1.5

    class FakeTicker:
        def __init__(self, _):
            pass

        def history(self, **_):
            return history

    import yfinance
    monkeypatch.setattr(yfinance, "Ticker", FakeTicker)
    dy = calibrate.dividend_yield_history("X.PA")
    assert dy.iloc[5] == 0.0
    assert dy.iloc[250] == pytest.approx((1.0 + 1.5) / 50 * 100)   # deux dividendes dans les 365 j
    assert dy.iloc[380] == pytest.approx(1.5 / 50 * 100)           # le premier est sorti de la fenêtre
