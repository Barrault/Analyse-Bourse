"""Tests de l'export des résultats du backtest complet."""
import json

from backtest import Backtester
from run_full_backtest import build_results, save_results


def test_results_are_written_to_a_missing_nested_directory(prices, no_fundamentals, tmp_path):
    backtester = Backtester()
    for seed, ticker in enumerate(["A.PA", "B.PA"]):
        backtester.add_price_data(ticker, prices(days=500, seed=seed, drift=0.001))
    backtester.benchmark_data = prices(days=500, seed=99)
    backtester.simulate("2023-12-01", "2030-12-31", ["A.PA", "B.PA"])

    path = save_results(build_results(backtester, "2023-12-01", "2030-12-31"), tmp_path / "results" / "r.json")

    written = json.loads(path.read_text(encoding="utf-8"))
    assert written["use_fundamentals"] is False
    assert written["final_portfolio_value"] == backtester.portfolio_history[-1].total_value
    assert set(written["strategy_metrics"]) == set(written["benchmark_metrics"])
