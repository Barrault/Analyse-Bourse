"""
Full backtest 2024-2026 with proper result saving
Run in background: python run_full_backtest.py > backtest_2024_2026.log 2>&1 &
"""
import sys
import io
import json
from datetime import datetime
from backtest import Backtester

if __name__ == "__main__":
    if sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    
    print("="*70)
    print("🚀 FULL BACKTEST 2024-2026")
    print("="*70)
    print(f"Start time: {datetime.now().isoformat()}")
    print("Running full 2-year backtest with monthly rebalancing...")
    print("(This may take 30-45 minutes)\n")
    
    backtester = Backtester(initial_cash=5000, min_order_amount=500)
    backtester.run_backtest(start_date="2024-07-01", end_date="2026-12-31")
    
    print("\n" + "="*70)
    print("✅ BACKTEST COMPLETE")
    print("="*70)
    backtester.print_summary()
    
    print(f"\nEnd time: {datetime.now().isoformat()}")
    
    # Sauvegarder les résultats en JSON
    results = {
        "period": "2024-07-01 to 2026-12-31",
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
    
    with open("backtest_results_2024_2026.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📁 Results saved to backtest_results_2024_2026.json")
