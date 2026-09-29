"""
Backtest complet avec journal et export JSON.

Lancement (depuis n'importe quel répertoire) : python src/run_full_backtest.py
Le journal est écrit dans logs_results/backtest.log et les résultats JSON dans
<output.results_dir>/<output.results_filename>, chemins relatifs à la racine du projet.
"""
import json
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from backtest import Backtester, performance_metrics
from config_loader import config

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class DualLogger:
    """Écrit la sortie à la fois dans la console et dans un fichier UTF-8."""
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


def build_results(backtester: Backtester, start_date: str, end_date: str) -> Dict[str, Any]:
    """Résumé JSON-sérialisable d'un backtest terminé."""
    last = backtester.portfolio_history[-1] if backtester.portfolio_history else None
    has_curve = len(backtester.equity_curve) > 1
    has_benchmark = len(backtester.benchmark_curve) > 1
    return {
        "period": f"{start_date} to {end_date}",
        "use_fundamentals": backtester.use_fundamentals,
        "initial_cash": backtester.initial_cash,
        "final_cash": last.cash if last else 0,
        "final_portfolio_value": last.total_value if last else 0,
        "pnl_absolute": last.total_value - backtester.initial_cash if last else 0,
        "pnl_percent": last.returns_pct if last else 0,
        "open_positions": len(last.positions) if last else 0,
        "total_trades": len(backtester.trades),
        "buy_trades": sum(1 for t in backtester.trades if t.side == "BUY"),
        "sell_trades": sum(1 for t in backtester.trades if t.side == "SELL"),
        "stop_loss_exits": sum(1 for t in backtester.trades if t.recommendation == "STOP-LOSS"),
        "total_fees": sum(t.fees for t in backtester.trades),
        "confidence_pnl_summary": backtester.get_confidence_pnl_summary(),
        "strategy_metrics": performance_metrics(backtester.equity_curve) if has_curve else None,
        "benchmark": backtester.benchmark_ticker,
        "benchmark_metrics": performance_metrics(backtester.benchmark_curve) if has_benchmark else None,
    }


def save_results(results: Dict[str, Any], path: Path) -> Path:
    """Écrit les résultats en JSON en créant le dossier si besoin (constat A5)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=float)
    return path


def main():
    log_dir = PROJECT_ROOT / "logs_results"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "backtest.log"

    logger = DualLogger(str(log_file))
    original_stderr = sys.stderr
    sys.stdout = logger
    sys.stderr = logger

    try:
        print("=" * 70)
        print("🚀 FULL BACKTEST")
        print("=" * 70)
        print(f"Start time: {datetime.now().isoformat()}")

        start_date = config.get('backtest.start_date')
        end_date = config.get('backtest.end_date')
        backtester = Backtester()
        print(f"Capital initial: {backtester.initial_cash}€, ordre min: {backtester.min_order_amount}€\n")
        backtester.run_backtest(start_date=start_date, end_date=end_date)

        print("\n" + "=" * 70)
        print("✅ BACKTEST COMPLETE")
        print("=" * 70)
        backtester.print_summary()
        print(f"\nEnd time: {datetime.now().isoformat()}")

        results_path = PROJECT_ROOT / config.get('output.results_dir') / config.get('output.results_filename')
        save_results(build_results(backtester, start_date, end_date), results_path)
        print(f"\n📁 Results saved to {results_path}")
        print(f"📄 Log file saved to {log_file}")
    except Exception:
        # Trace dans le journal AVANT de restaurer stderr, sinon elle n'y figurerait pas
        traceback.print_exc()
        raise
    finally:
        sys.stdout, sys.stderr = logger.console, original_stderr
        logger.close()


if __name__ == "__main__":
    main()
