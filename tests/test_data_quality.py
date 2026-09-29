"""Tests du contrôle qualité des cours (sauts aberrants, cf. DEC-17)."""
import pandas as pd
import pytest

from backtest import Backtester
from cac40_analyzer import prepare_indicators, prepare_indicators_by_segment, split_anomalies


def with_jump(df, at, factor):
    df = df.copy()
    df.loc[df.index[at]:, ["Open", "High", "Low", "Close"]] *= factor
    return df


def test_bogus_jumps_are_detected(prices):
    df = prices(days=300)
    assert list(split_anomalies(with_jump(df, 200, 86), "ATO.PA")) == [df.index[200]]  # regroupement
    assert len(split_anomalies(with_jump(df, 150, 1 / 4.5), "VIV.PA")) == 1           # scission


def test_verified_real_moves_are_not_flagged(prices):
    assert split_anomalies(with_jump(prices(days=300), 200, 2.2), "ETL.PA").empty


def test_indicators_never_mix_two_price_scales(prices):
    df = with_jump(prices(days=700), 400, 86)
    anomalies = split_anomalies(df, "ATO.PA")
    indicators = prepare_indicators_by_segment(df, anomalies)

    before = indicators[indicators.index < df.index[400]]
    after = indicators[indicators.index >= df.index[400]]
    # Avant le saut : identique à un calcul qui ignore tout du futur
    pd.testing.assert_frame_equal(before, prepare_indicators(df.iloc[:400]), check_freq=False)
    # Après : pas de ligne tant que le nouveau segment n'a pas 200 séances
    assert after.index[0] >= df.index[400 + 199]


def test_held_position_is_closed_at_last_valid_price_on_a_bogus_jump(prices, no_fundamentals):
    df = with_jump(prices(days=700), 400, 86)
    backtester = Backtester()
    backtester.add_price_data("ATO.PA", df)
    backtester._execute_buy("ATO.PA", {"company_name": "Atos", "price": 100.0, "confidence": 1.0},
                            df.index[390])

    backtester._exit_on_price_anomaly(df.index[400])

    assert "ATO.PA" not in backtester.positions
    assert backtester.trades[-1].recommendation == "OST"
    assert backtester.trades[-1].price == pytest.approx(df["Close"].iloc[399])


def test_no_trade_when_signal_and_execution_straddle_a_jump(prices, no_fundamentals):
    df = with_jump(prices(days=700), 400, 86)
    backtester = Backtester()
    backtester.add_price_data("ATO.PA", df)
    assert backtester.analyze_on_date("ATO.PA", df.index[400]) is None
    assert backtester.analyze_on_date("ATO.PA", df.index[399]) is not None
