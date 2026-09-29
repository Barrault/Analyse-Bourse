"""
Calibrage du score et de la confiance, avec séparation stricte apprentissage / test.

    python src/calibrate.py features    # effet de chaque composante (apprentissage)
    python src/calibrate.py calibrate   # table score technique -> probabilité (apprentissage)
    python src/calibrate.py evaluate    # fiabilité de cette table (test, hors échantillon)

Mesure commune : le rendement du titre relatif à l'ETF CAC 40 sur `calibration.horizon_days`
séances, de l'ouverture du jour du signal à la clôture de fin d'horizon. Voir DEC-18 à DEC-22.
"""
import argparse
import contextlib
import io
import sys
from typing import Callable, Dict, List, Tuple

import numpy as np
import pandas as pd

from backtest import Backtester
from cac40_analyzer import NOMS_ENTREPRISES, IndicatorSnapshot
from config_loader import config

# Composantes techniques du score : (clé de poids dans scoring.*, condition, signe attendu).
# Le signe attendu est celui du poids actuel : +1 si la condition doit prédire une
# surperformance, -1 une sous-performance.
def _rsi(key):
    return config.get(f'indicators.rsi.{key}')

COMPONENTS: List[Tuple[str, Callable[[IndicatorSnapshot], bool], int]] = [
    ("trends.long_term", lambda s: s.close > s.sma200, +1),
    ("trends.mid_term", lambda s: s.sma50 > s.sma200, +1),
    ("trends.short_term", lambda s: s.sma20 > s.sma50, +1),
    ("momentum.macd_line", lambda s: s.macd > 0, +1),
    ("momentum.macd_histogram", lambda s: s.macd_hist > 0, +1),
    ("rsi.neutral_zone", lambda s: _rsi('neutral_lower') <= s.rsi14 <= _rsi('neutral_upper'), +1),
    ("rsi.oversold", lambda s: s.rsi14 < _rsi('oversold_threshold'), +1),
    ("rsi.overbought", lambda s: s.rsi14 > _rsi('overbought_threshold'), -1),
    ("bollinger.above_upper", lambda s: s.close > s.bb_upper, +1),
    ("bollinger.below_lower", lambda s: s.close < s.bb_lower, -1),
    ("volume.high_volume", lambda s: s.vol > s.vol_sma20, +1),
    ("volatility.low_volatility", lambda s: s.atr14 / s.close < config.get('scoring.volatility.threshold'), +1),
]


# ----------------------- Observations ----------------------- #

def forward_excess_return(backtester: Backtester, ticker: str, date: pd.Timestamp,
                          entry_price: float, horizon: int) -> float:
    """Rendement (en %) du titre moins celui du benchmark, de l'ouverture de `date` à la
    clôture `horizon` séances plus tard (calendrier du benchmark). NaN si l'horizon dépasse
    les données ou traverse un saut de cours aberrant."""
    bench = backtester.benchmark_data
    if date not in bench.index:
        return np.nan
    position = bench.index.get_loc(date) + horizon
    if position >= len(bench.index):
        return np.nan
    end = bench.index[position]
    anomalies = backtester.anomalies.get(ticker, pd.DatetimeIndex([]))
    if ((anomalies > date) & (anomalies <= end)).any():
        return np.nan
    stock_end = backtester.all_data[ticker]['Close'].asof(end)
    bench_return = bench['Close'].loc[end] / bench['Open'].loc[date] - 1
    return (stock_end / entry_price - 1 - bench_return) * 100


def observations(backtester: Backtester, start: str, end: str, horizon: int) -> pd.DataFrame:
    """Une ligne par (date de rebalance, titre analysable) : composantes, score technique,
    rendement relatif futur et son rang percentile dans le mois (robuste aux extrêmes)."""
    rows = []
    for date in backtester.rebalance_dates(start, end, "month"):
        for ticker in backtester.indicators:
            analysis = backtester.analyze_on_date(ticker, date)
            if analysis is None:
                continue
            snap = analysis["snapshot"]
            row = {"date": date, "ticker": ticker, "technical_score": analysis["technical_score"],
                   "excess": forward_excess_return(backtester, ticker, date, analysis["price"], horizon)}
            row.update({key: bool(condition(snap)) for key, condition, _ in COMPONENTS})
            rows.append(row)
    df = pd.DataFrame(rows).dropna(subset=["excess"])
    df["rank"] = df.groupby("date")["excess"].rank(pct=True) * 100
    return df.reset_index(drop=True)


# ----------------------- Statistiques ----------------------- #

def monthly_spread(df: pd.DataFrame, mask: pd.Series, column: str = "rank") -> Tuple[float, float, int]:
    """Écart moyen (condition vraie − fausse) de `column`, calculé mois par mois, puis
    moyenne et t de Student sur les mois : les titres d'un même mois ne sont pas
    indépendants (même marché), les mois le sont à peu près."""
    spreads = []
    for _, month in df.groupby("date"):
        on = mask.loc[month.index]
        if on.sum() >= 3 and (~on).sum() >= 3:
            spreads.append(month.loc[on, column].mean() - month.loc[~on, column].mean())
    spreads = np.array(spreads)
    if len(spreads) < 2:
        return np.nan, np.nan, len(spreads)
    return spreads.mean(), spreads.mean() / (spreads.std(ddof=1) / np.sqrt(len(spreads))), len(spreads)


def keep_component(spread: float, t_stat: float, expected_sign: int, min_t: float) -> bool:
    """Règle fixée a priori : effet du signe attendu, et t >= min_t."""
    return bool(np.sign(spread) == expected_sign and abs(t_stat) >= min_t)


def isotonic_increasing(values: List[float], weights: List[float]) -> List[float]:
    """Régression isotone (pool adjacent violators) : la suite croissante la plus proche,
    pondérée. Garantit qu'un score plus haut n'a jamais une probabilité plus basse."""
    blocks = [[v, w, 1] for v, w in zip(values, weights)]  # [moyenne, poids, nb de cases]
    merged = []
    for block in blocks:
        merged.append(block)
        while len(merged) > 1 and merged[-2][0] > merged[-1][0]:
            (v2, w2, n2), (v1, w1, n1) = merged.pop(), merged.pop()
            merged.append([(v1 * w1 + v2 * w2) / (w1 + w2), w1 + w2, n1 + n2])
    return [v for v, _, n in merged for _ in range(n)]


def calibration_table(df: pd.DataFrame, n_bins: int) -> Dict[str, list]:
    """Tranches de score (quantiles) et probabilité de battre le benchmark dans chacune."""
    scores = df["technical_score"]
    edges = sorted(set(np.round(scores.quantile(np.linspace(0, 1, n_bins + 1)[1:-1]).values, 2)))
    bins = np.searchsorted(edges, scores, side="right")
    beat = df["excess"] > 0
    freq = [float(beat[bins == b].mean()) for b in range(len(edges) + 1)]
    counts = [int((bins == b).sum()) for b in range(len(edges) + 1)]
    return {"score_edges": [float(e) for e in edges],
            "probabilities": [round(p, 3) for p in isotonic_increasing(freq, counts)],
            "raw_frequencies": [round(f, 3) for f in freq], "counts": counts}


# ----------------------- Commandes ----------------------- #

def load() -> Backtester:
    backtester = Backtester()
    with contextlib.redirect_stdout(io.StringIO()):
        backtester.load_data(list(NOMS_ENTREPRISES))
    return backtester


def cmd_features(backtester: Backtester):
    start, end = config.get('calibration.train_start'), config.get('calibration.train_end')
    df = observations(backtester, start, end, config.get('calibration.horizon_days'))
    min_t = config.get('calibration.min_t')
    print(f"Apprentissage {start} → {end} : {len(df)} observations, {df.date.nunique()} mois")
    print("Écart de rang percentile (0-100) du rendement relatif à 3 mois, condition vraie − fausse\n")
    print(f"{'Composante':<28}{'poids':>7}{'% vrai':>8}{'écart':>8}{'t':>6}  décision")
    for key, _, sign in COMPONENTS:
        spread, t_stat, _ = monthly_spread(df, df[key])
        keep = keep_component(spread, t_stat, sign, min_t)
        print(f"{key:<28}{config.get('scoring.' + key):>+7.1f}{df[key].mean() * 100:>7.0f}%"
              f"{spread:>+8.2f}{t_stat:>6.1f}  {'garder' if keep else 'poids -> 0'}")


def cmd_calibrate(backtester: Backtester):
    start, end = config.get('calibration.train_start'), config.get('calibration.train_end')
    df = observations(backtester, start, end, config.get('calibration.horizon_days'))
    table = calibration_table(df, n_bins=5)
    print(f"Apprentissage {start} → {end} : {len(df)} observations")
    print(f"Probabilité de base de battre le benchmark : {(df.excess > 0).mean():.3f}")
    for key in ("counts", "raw_frequencies"):
        print(f"{key}: {table[key]}")
    print("\nÀ reporter dans config.yaml (scoring.confidence_calibration) :")
    print(f"    score_edges: {table['score_edges']}")
    print(f"    probabilities: {table['probabilities']}")


def cmd_evaluate(backtester: Backtester):
    start, end = config.get('backtest.start_date'), config.get('backtest.end_date')
    df = observations(backtester, start, end, config.get('calibration.horizon_days'))
    calib = config.get('scoring.confidence_calibration')
    df["bin"] = np.searchsorted(calib["score_edges"], df["technical_score"], side="right")
    df["p"] = [calib["probabilities"][b] for b in df["bin"]]
    print(f"Test {start} → {end} : {len(df)} observations, {df.date.nunique()} mois")
    print(f"Probabilité de base de battre le benchmark : {(df.excess > 0).mean():.3f}\n")
    print(f"{'tranche':>8}{'n':>7}{'prévue':>9}{'observée':>10}{'rang moyen':>12}")
    for b, group in df.groupby("bin"):
        print(f"{b:>8}{len(group):>7}{group.p.iloc[0]:>9.3f}{(group.excess > 0).mean():>10.3f}{group['rank'].mean():>12.1f}")
    top = df["bin"] == df["bin"].max()
    spread, t_stat, months = monthly_spread(df, top)
    print(f"\nTranche haute − reste : {spread:+.2f} pts de rang (t = {t_stat:.1f}, {months} mois)")
    print(f"Corrélation de rang score ↔ rendement relatif : {df.technical_score.rank().corr(df.excess.rank()):+.3f}")


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["features", "calibrate", "evaluate"])
    command = parser.parse_args().command
    backtester = load()
    {"features": cmd_features, "calibrate": cmd_calibrate, "evaluate": cmd_evaluate}[command](backtester)


if __name__ == "__main__":
    main()
