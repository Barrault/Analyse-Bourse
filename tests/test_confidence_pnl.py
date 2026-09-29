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

    high_bucket = next(item for item in summary if item["label"] == "0.900")
    low_bucket = next(item for item in summary if item["label"] == "0.100")

    assert high_bucket["trades"] == 1
    assert high_bucket["wins"] == 1
    assert high_bucket["win_rate"] == 100.0
    assert low_bucket["trades"] == 1
    assert low_bucket["wins"] == 0
    assert low_bucket["win_rate"] == 0.0


def test_round_trip_pnl_is_net_of_both_buy_and_sell_fees():
    # Vente brute (101,5) > achat + frais (101), mais vente nette (100,5) < coût : c'est une perte.
    # L'ancien win rate (brut vs net) la comptait comme un gain (constat B5).
    backtester = Backtester(initial_cash=1000, min_order_amount=10)
    backtester.trades.extend([
        Trade(date=None, ticker="X", company_name="X", side="BUY", quantity=1, price=100,
              amount=100, fees=1, net_cost=101, recommendation="ACHAT", confidence=0.5,
              entry_confidence=0.5),
        Trade(date=None, ticker="X", company_name="X", side="SELL", quantity=1, price=101.5,
              amount=101.5, fees=1, net_cost=100.5, recommendation="VENTE", confidence=0.0,
              entry_confidence=0.5),
    ])

    (round_trip,) = backtester.closed_trades()
    assert round_trip["pnl"] == -0.5
    (bucket,) = backtester.get_confidence_pnl_summary()
    assert bucket["losses"] == 1 and bucket["wins"] == 0
