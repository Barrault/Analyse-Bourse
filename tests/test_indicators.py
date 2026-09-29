"""Tests des indicateurs et de la préparation des données."""
import numpy as np
import pandas as pd

from cac40_analyzer import flatten_columns, rsi


def test_flatten_columns_picks_the_price_level_of_a_multiindex():
    columns = pd.MultiIndex.from_product([["Close", "Volume"], ["AC.PA"]], names=["Price", "Ticker"])
    df = pd.DataFrame([[1.0, 10], [2.0, 20]], columns=columns)
    assert list(flatten_columns(df).columns) == ["Close", "Volume"]


def test_flatten_columns_leaves_flat_frames_untouched():
    df = pd.DataFrame({"Close": [1.0]})
    assert list(flatten_columns(df).columns) == ["Close"]


def test_rsi_stays_within_bounds():
    prices = pd.Series(100 + np.cumsum(np.random.default_rng(0).normal(size=300)))
    values = rsi(prices).dropna()
    assert values.between(0, 100).all()
