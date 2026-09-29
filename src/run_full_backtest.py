"""
Full backtest 2024-2026 with proper result saving
Run (depuis n'importe quel répertoire) : python src/run_full_backtest.py
Le log est écrit dans logs_results/backtest.log et les résultats JSON dans
<output.results_dir>/<output.results_filename>, chemins relatifs à la racine du projet.
"""
import sys
import json
from pathlib import Path
from datetime import datetime
from backtest import Backtester
from config_loader import config

PROJECT_ROOT = Path(__file__).resolve().parent.parent

class DualLogger:
    """Writes output to both console and log file with UTF-8 encoding"""
    def __init__(self, log_file):
        self.log_file = log_file
        self.console = sys.stdout
        self.file = open(log_file, 'w', encoding='utf-8', errors='replace')

    def write(self, message):
        self.console.write(message)
        self.console.flush()
        self.file.write(message)
        self.file.flush()

    def flush(self):
        self.console.flush()
        self.file.flush()

    def close(self):
        self.file.close()

if __name__ == "__main__":
    # Set up UTF-8 logging
    log_dir = PROJECT_ROOT / "logs_results"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "backtest.log"

    # Redirect stdout to our dual logger
    logger = DualLogger(str(log_file))
    original_stderr = sys.stderr
    sys.stdout = logger
    sys.stderr = logger

    try:
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
        # Chemin ancré sur la racine du projet et dossier créé à l'avance : un run de
        # 30 minutes ne doit pas échouer à l'écriture finale (constat A5).
        results_path = PROJECT_ROOT / config.get('output.results_dir') / config.get('output.results_filename')
        results_path.parent.mkdir(parents=True, exist_ok=True)

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
            "confidence_pnl_summary": backtester.get_confidence_pnl_summary(),
        }

        with open(f"{results_dir}/{results_filename}", "w", encoding='utf-8') as f:
            json.dump(results, f, indent=2)

        print(f"\n📁 Results saved to {results_dir}/{results_filename}")
        print(f"📄 Log file saved to {log_file}")

    finally:
        sys.stdout, sys.stderr = logger.console, original_stderr
        logger.close()
