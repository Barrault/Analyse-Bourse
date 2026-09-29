"""Test de bout en bout contre Yahoo Finance (réseau requis).

Exclu par défaut ; lancer avec : pytest -m network
"""
import pandas as pd
import pytest

from backtest import Backtester

pytestmark = pytest.mark.network


def test_download_prepare_and_analyze_one_ticker():
    backtester = Backtester()
    backtester.use_fundamentals = True
    backtester.load_data(["AC.PA"], period="2y")

    assert "AC.PA" in backtester.indicators
    analysis = backtester.analyze_on_date("AC.PA", backtester.all_data["AC.PA"].index[-1])

    assert analysis is not None
    assert analysis["recommendation"] in {"ACHAT", "NEUTRE", "VENTE"}
    assert 0.0 <= analysis["confidence"] <= 1.0
    assert isinstance(analysis["date"], pd.Timestamp)
