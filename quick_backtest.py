"""
Quick backtest - 3 mois seulement pour tester
"""
import sys
import io
from backtest import Backtester

if __name__ == "__main__":
    if sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    backtester = Backtester(initial_cash=5000, min_order_amount=500)
    backtester.run_backtest(start_date="2024-07-01", end_date="2024-09-30")  # 3 mois
    backtester.print_summary()
