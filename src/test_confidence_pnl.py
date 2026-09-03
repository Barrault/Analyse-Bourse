import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backtest import Backtester, Trade


def test_confidence_pnl_summary_groups_trades_by_buy_confidence():
    backtester = Backtester(initial_cash=1000, min_order_amount=10)

    buy_high = Trade(
        date=None,
        ticker="AAPL",
        company_name="Apple",
        side="BUY",
        quantity=1,
        price=100,
        amount=100,
        fees=1,
        net_cost=101,
        recommendation="ACHAT",
        confidence=0.9,
    )
    buy_low = Trade(
        date=None,
        ticker="MSFT",
        company_name="Microsoft",
        side="BUY",
        quantity=1,
        price=100,
        amount=100,
        fees=1,
        net_cost=101,
        recommendation="ACHAT",
        confidence=0.1,
    )
    sell_high = Trade(
        date=None,
        ticker="AAPL",
        company_name="Apple",
        side="SELL",
        quantity=1,
        price=120,
        amount=120,
        fees=1,
        net_cost=119,
        recommendation="VENTE",
        confidence=0.0,
        entry_confidence=0.9,
    )
    sell_low = Trade(
        date=None,
        ticker="MSFT",
        company_name="Microsoft",
        side="SELL",
        quantity=1,
        price=90,
        amount=90,
        fees=1,
        net_cost=89,
        recommendation="VENTE",
        confidence=0.0,
        entry_confidence=0.1,
    )

    backtester.trades.extend([buy_high, buy_low, sell_high, sell_low])

    summary = backtester.get_confidence_pnl_summary()

    high_bucket = next(item for item in summary if item["label"] == "0.80-1.00")
    low_bucket = next(item for item in summary if item["label"] == "0.00-0.20")

    assert high_bucket["trades"] == 1
    assert high_bucket["wins"] == 1
    assert high_bucket["win_rate"] == 100.0
    assert low_bucket["trades"] == 1
    assert low_bucket["wins"] == 0
    assert low_bucket["win_rate"] == 0.0
