"""
Full backtest 2024-2026 with proper result saving
Run in background: python run_full_backtest.py > backtest_2024_2026.log 2>&1 &
"""
import sys
import io
import json
from datetime import datetime
from backtest import Backtester
from config_loader import config

if __name__ == "__main__":
    # Force UTF-8 for redirected logs
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

    print("="*70)
    print("🚀 FULL BACKTEST")
    print("="*70)
    print(f"Start time: {datetime.now().isoformat()}")

    # Charger les paramètres depuis la configuration
    backtest_params = config.get_section('backtest')
    trading_params = config.get_section('trading')

    start_date = backtest_params['start_date']
    end_date = backtest_params['end_date']
    initial_cash = trading_params['initial_cash']
    min_order_amount = trading_params['min_order_amount']

    print(f"Running backtest from {start_date} to {end_date}")
    print(f"Initial capital: {initial_cash}€, Min order: {min_order_amount}€")
    print("(This may take 30-45 minutes)\n")

    backtester = Backtester(initial_cash=initial_cash, min_order_amount=min_order_amount)
    backtester.run_backtest(start_date=start_date, end_date=end_date)

    print("\n" + "="*70)
    print("✅ BACKTEST COMPLETE")
    print("="*70)
    backtester.print_summary()

    print(f"\nEnd time: {datetime.now().isoformat()}")

    # Sauvegarder les résultats en JSON
    output_params = config.get_section('output')
    results_dir = output_params['results_dir']
    results_filename = output_params['results_filename']

    results = {
        "period": f"{start_date} to {end_date}",
        "initial_cash": backtester.initial_cash,
        "final_cash": backtester.portfolio_history[-1].cash if backtester.portfolio_history else 0,
        "total_trades": len(backtester.trades),
        "buy_trades": len([t for t in backtester.trades if t.side == "BUY"]),
        "sell_trades": len([t for t in backtester.trades if t.side == "SELL"]),
        "total_fees": sum(t.fees for t in backtester.trades),
        "final_portfolio_value": backtester.portfolio_history[-1].total_value if backtester.portfolio_history else 0,
        "pnl_absolute": backtester.portfolio_history[-1].total_value - backtester.initial_cash if backtester.portfolio_history else 0,
        "pnl_percent": backtester.portfolio_history[-1].returns_pct if backtester.portfolio_history else 0,
        "open_positions": len(backtester.portfolio_history[-1].positions) if backtester.portfolio_history else 0,
    }

    with open(f"{results_dir}/{results_filename}", "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n📁 Results saved to {results_dir}/{results_filename}")
