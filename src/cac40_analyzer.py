"""
CAC40 Stock Analyzer - Version stricte
"""
# -*- coding: utf-8 -*-
import argparse
import sys
from dataclasses import dataclass
from typing import Optional, Dict, Any, List

import numpy as np
import pandas as pd
import yfinance as yf

# Import configuration
from config_loader import config

# ----------------------- Helpers: Indicators ----------------------- #

def sma(series: pd.Series, window: int) -> pd.Series:
    """Calcule la Moyenne Mobile Simple (SMA) sur une fenêtre donnée."""
    return series.rolling(window).mean()

def ema(series: pd.Series, window: int) -> pd.Series:
    """Calcule la Moyenne Mobile Exponentielle (EMA) sur une fenêtre donnée."""
    return series.ewm(span=window, adjust=False).mean()

def rsi(series: pd.Series, window: int = 14) -> pd.Series:
    """Calcule l’indice de force relative (RSI), indicateur de momentum."""
    delta = series.diff()
    gain = np.where(delta > 0, delta, 0.0).flatten()
    loss = np.where(delta < 0, -delta, 0.0).flatten()
    roll_up = pd.Series(gain, index=series.index).ewm(alpha=1/window, adjust=False).mean()
    roll_down = pd.Series(loss, index=series.index).ewm(alpha=1/window, adjust=False).mean()
    rs = roll_up / (roll_down + 1e-12)
    rsi = 100 - (100 / (1 + rs))
    return rsi

def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """Calcule l’indicateur MACD et sa ligne de signal (momentum à court/moyen terme)."""
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist

def bollinger(series: pd.Series, window: int = 20, num_std: float = 2.0):
    """Calcule les bandes de Bollinger (moyenne ± n écarts-types)."""
    mid = sma(series, window)
    std = series.rolling(window).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    return mid, upper, lower

def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """Calcule la True Range (amplitude réelle des variations de prix)."""
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    return tr

def atr(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
    """Calcule l’Average True Range (ATR), mesure de volatilité."""
    tr = true_range(high, low, close)
    return tr.ewm(alpha=1/window, adjust=False).mean()

# ----------------------- Data Quality ----------------------- #

def price_anomalies(df: pd.DataFrame, max_daily_factor: float) -> pd.DatetimeIndex:
    """Séances où la clôture est multipliée ou divisée par au moins `max_daily_factor`."""
    log_moves = np.log(df['Close'] / df['Close'].shift(1)).abs()
    return df.index[log_moves >= np.log(max_daily_factor)]


def split_anomalies(df: pd.DataFrame, ticker: str) -> pd.DatetimeIndex:
    """Sauts de cours aberrants d'un titre, hors mouvements réels vérifiés (cf. DEC-17).

    Un facteur >= 2 en une séance trahit presque toujours une opération sur titre mal
    ajustée par Yahoo (regroupement d'actions, scission) : les cours d'avant et d'après
    ne sont pas sur la même échelle.
    """
    if ticker in config.get('data_quality.verified_real_moves'):
        return pd.DatetimeIndex([])
    return price_anomalies(df, config.get('data_quality.max_daily_factor'))


def prepare_indicators_by_segment(df: pd.DataFrame, anomalies: pd.DatetimeIndex) -> Optional[pd.DataFrame]:
    """Indicateurs calculés séparément sur chaque segment compris entre deux sauts aberrants.

    À une date donnée, les indicateurs ne dépendent que du segment en cours : aucune
    moyenne mobile ne mélange deux échelles de prix, et un saut FUTUR n'a aucun effet
    sur le passé (pas d'anticipation). Un segment trop court pour la SMA200 ne produit
    aucune ligne : le titre n'est simplement pas analysable pendant ce temps.
    """
    bounds = [df.index[0], *anomalies, df.index[-1] + pd.Timedelta(days=1)]
    segments = [prepare_indicators(df[(df.index >= lo) & (df.index < hi)]) for lo, hi in zip(bounds, bounds[1:])]
    segments = [seg for seg in segments if seg is not None and not seg.empty]
    return pd.concat(segments) if segments else None


# ----------------------- Indicator Preparation ----------------------- #

PRICE_COLUMNS = ('Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume')

def flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Aplatit les colonnes MultiIndex renvoyées par yf.download (niveau 'Price', 'Ticker')."""
    df = df.copy()
    if df.columns.nlevels > 1:
        level = next(
            (lvl for lvl in range(df.columns.nlevels)
             if any(v in PRICE_COLUMNS for v in df.columns.get_level_values(lvl))),
            -1,
        )
        df.columns = df.columns.get_level_values(level)
    return df

def prepare_indicators(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """Prépare les indicateurs techniques pour un DataFrame."""
    if df is None or df.empty:
        return None

    df = flatten_columns(df)

    required_cols = ['Close', 'High', 'Low', 'Volume']
    for col in required_cols:
        if col not in df.columns:
            return None

    sma_params = config.get_section('indicators')['sma']
    rsi_params = config.get_section('indicators')['rsi']
    bb_params = config.get_section('indicators')['bollinger']
    atr_params = config.get_section('indicators')['atr']
    vol_params = config.get_section('indicators')['volume']

    df['SMA20'] = sma(df['Close'], sma_params['short_window'])
    df['SMA50'] = sma(df['Close'], sma_params['mid_window'])
    df['SMA200'] = sma(df['Close'], sma_params['long_window'])
    df['RSI14'] = rsi(df['Close'], rsi_params['window'])

    macd_params = config.get_section('indicators')['macd']
    macd_line, signal_line, hist = macd(
        df['Close'], macd_params['fast_window'], macd_params['slow_window'], macd_params['signal_window']
    )
    df['MACD'] = macd_line
    df['MACD_signal'] = signal_line
    df['MACD_hist'] = hist

    bb_mid, bb_upper, bb_lower = bollinger(df['Close'], bb_params['window'], bb_params['num_std'])
    df['BB_mid'] = bb_mid
    df['BB_upper'] = bb_upper
    df['BB_lower'] = bb_lower
    df['ATR14'] = atr(df['High'], df['Low'], df['Close'], atr_params['window'])
    df['VOL_SMA20'] = sma(df['Volume'], vol_params['sma_window'])

    return df.dropna()

# ----------------------- Scoring & Recommendation ----------------------- #

def outperformance_probability(technical_score: float) -> float:
    """Probabilité historique de battre l'ETF CAC 40 à ~3 mois pour ce niveau de score
    technique, lue dans la table calibrée sur la période d'apprentissage (cf. DEC-20)."""
    calibration = config.get('scoring.confidence_calibration')
    tranche = int(np.searchsorted(calibration['score_edges'], technical_score, side='right'))
    return float(calibration['probabilities'][tranche])


def order_amount() -> float:
    """Montant de chaque achat : identique pour tous les signaux (cf. DEC-21).

    La confiance calibrée varie trop peu (≈ 44 % à 49 %) pour justifier des montants
    différents ; des lignes de même taille évitent aussi de concentrer le risque.
    """
    return float(config.get('trading.order_amount'))


@dataclass
class IndicatorSnapshot:
    """Structure stockant un ensemble d’indicateurs techniques et fondamentaux."""
    date: pd.Timestamp
    close: float
    sma20: float
    sma50: float
    sma200: float
    rsi14: float
    macd: float
    macd_signal: float
    macd_hist: float
    bb_mid: float
    bb_upper: float
    bb_lower: float
    atr14: float
    vol: float
    vol_sma20: float
    fundamentals: Dict[str, Optional[float]]


def compute_score(s: IndicatorSnapshot) -> Dict[str, Any]:
    """
    Score technique (tendances, momentum, volume), recommandation, confiance calibrée,
    filtre « entreprise en perte » et fondamentaux affichés pour information.
    """
    weights = config.get_section('scoring')
    score = 0
    reasons: List[str] = []

    def add(points: float, reason: str):
        """Ajoute une contribution ; une composante de poids nul n'a ni effet ni motif
        affiché (poids mis à 0 faute d'effet mesuré, cf. DEC-19)."""
        nonlocal score
        if points:
            score += points
            reasons.append(reason)

    trends, momentum = weights['trends'], weights['momentum']
    if s.close > s.sma200:
        add(trends['long_term'], "+ Tendance long terme : Le prix de l'action a augmenté ces derniers mois, montrant que les investisseurs sont confiants.")
    else:
        add(-trends['long_term'], "- Tendance long terme : Le prix de l'action a baissé ces derniers mois, montrant que les investisseurs sont moins confiants.")

    if s.sma50 > s.sma200:
        add(trends['mid_term'], "+ Tendance moyen terme : Le prix de l'action a augmenté ces dernières semaines.")
    else:
        add(-trends['mid_term'], "- Tendance moyen terme : Le prix de l'action stagne ou baisse ces dernières semaines.")

    if s.sma20 > s.sma50:
        add(trends['short_term'], "+ Tendance court terme : Le prix de l'action a augmenté ces derniers jours, montrant un élan récent.")
    else:
        add(-trends['short_term'], "- Tendance court terme : Le prix de l'action baisse ou stagne ces derniers jours.")

    if s.macd > 0:
        add(momentum['macd_line'], "+ Momentum : Le prix de l'action continue de monter récemment, les acheteurs sont actifs.")
    else:
        add(-momentum['macd_line'], "- Momentum : Le prix de l'action pourrait ralentir ou baisser, prudence.")

    if s.macd_hist > 0:
        add(momentum['macd_histogram'], "+ Accélération : Le mouvement haussier s'accélère, montrant un fort intérêt.")
    else:
        add(-momentum['macd_histogram'], "- Accélération : Le mouvement haussier ralentit ou le prix baisse.")

    rsi_params = config.get_section('indicators')['rsi']
    if rsi_params['neutral_lower'] <= s.rsi14 <= rsi_params['neutral_upper']:
        add(weights['rsi']['neutral_zone'], "* RSI normal : Le prix est équilibré, ni trop acheté ni trop vendu.")
    elif s.rsi14 < rsi_params['oversold_threshold']:
        add(weights['rsi']['oversold'], "* RSI bas : Le prix a beaucoup baissé, possibilité de rebond.")
    elif s.rsi14 > rsi_params['overbought_threshold']:
        add(weights['rsi']['overbought'], "- RSI haut : Le prix a beaucoup monté, risque de correction.")

    if s.close > s.bb_upper:
        add(weights['bollinger']['above_upper'], "+ Prix élevé récemment : Le prix monte plus que d'habitude, beaucoup d'intérêt des investisseurs.")
    elif s.close < s.bb_lower:
        add(weights['bollinger']['below_lower'], "- Prix bas récemment : Le prix descend plus que d'habitude, possible manque d'intérêt ou ventes fortes.")

    if s.vol is not None and s.vol_sma20 is not None:
        if s.vol > s.vol_sma20:
            add(weights['volume']['high_volume'], "+ Volume élevé : Beaucoup d'achats et ventes, le mouvement est soutenu.")
        else:
            add(weights['volume']['low_volume'], "- Volume faible : Peu d'investisseurs bougent, le mouvement manque de soutien.")

    if s.atr14 / s.close < weights['volatility']['threshold']:
        add(weights['volatility']['low_volatility'], "+ Volatilité faible : Le prix varie peu, risque limité.")
    else:
        add(weights['volatility']['high_volatility'], "* Volatilité élevée : Le prix peut beaucoup bouger, prudence.")

    # ----------------------- Recommandation ----------------------- #
    # La décision ne repose que sur le score technique, le seul dont l'effet est mesuré :
    # l'analyse du jour applique exactement la stratégie évaluée par le backtest (DEC-24).
    technical_score = score
    thresholds = config.get('scoring.thresholds')
    if score >= thresholds['buy']:
        rec = "ACHAT"
    elif score <= thresholds['sell']:
        rec = "VENTE"
    else:
        rec = "NEUTRE"

    # ----------------------- Fondamentaux ----------------------- #
    # Non testables (pas d'historique gratuit) : information seulement, sauf un filtre de
    # prudence qui écarte l'achat d'une entreprise en perte (DEC-24).
    pe = s.fundamentals.get("trailingPE")
    pb = s.fundamentals.get("priceToBook")
    dy = s.fundamentals.get("dividendYield")
    eps = s.fundamentals.get("trailingEps")
    # yfinance ne publie pas de PE négatif (trailingPE = None) : une perte se lit sur le BPA.
    loss_making = (eps is not None and eps < 0) or (pe is not None and pe < 0)
    if loss_making:
        if rec == "ACHAT" and config.get('fundamentals.exclude_loss_making'):
            rec = "NEUTRE"
            reasons.append("-- Achat écarté : l'entreprise est en perte (BPA négatif). Filtre de prudence.")
        else:
            reasons.append("- Entreprise en perte (BPA négatif).")
    if any(v is not None for v in (pe, pb, dy)):
        def fmt(value, suffix=""):
            return "n.d." if value is None else f"{value:.1f}{suffix}"
        reasons.append(f"* Fondamentaux (information, sans effet sur la décision) : PE {fmt(pe)} | "
                       f"P/B {fmt(pb)} | dividende {fmt(dy, ' %')}")

    # Confiance = probabilité mesurée que la recommandation soit dans le bon sens (DEC-20) :
    # battre le CAC 40 à 3 mois pour un ACHAT (ou un NEUTRE), le sous-performer pour une VENTE.
    p_outperform = outperformance_probability(technical_score)
    confidence = 1 - p_outperform if rec == "VENTE" else p_outperform
    base_rate = config.get('scoring.confidence_calibration.base_rate')
    reasons.append(f"* Historiquement, {p_outperform:.0%} des titres à ce niveau de score technique ont battu "
                   f"le CAC 40 à 3 mois (moyenne tous titres : {base_rate:.0%}).")

    # Un montant n'a de sens que pour un achat ; même règle que le backtest (cf. DEC-07)
    suggested_amount = order_amount() if rec == "ACHAT" else 0.0

    return {
        "score": score,
        "technical_score": technical_score,
        "recommendation": rec,
        "confidence": round(confidence, 3),
        "p_outperform": p_outperform,
        "suggested_amount": suggested_amount,
        "reasons": reasons
    }

# ----------------------- Fundamentals & Snapshot ----------------------- #

FUNDAMENTAL_KEYS = ("trailingPE", "priceToBook", "dividendYield", "trailingEps")

def fetch_fundamentals_safe(ticker: str) -> Dict[str, Optional[float]]:
    """Récupère les fondamentaux d’un ticker Yahoo Finance, avec conversion sécurisée."""
    def to_float(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return None

    try:
        info = yf.Ticker(ticker).info
    except Exception:
        return dict.fromkeys(FUNDAMENTAL_KEYS)

    # Déjà exprimé en pourcentage depuis yfinance 0.2.54 (4.5 = 4,5 %)
    dy = to_float(info.get("dividendYield"))
    # yfinance renvoie None (et non 0) pour un non-payeur : le dividende annuel versé tranche.
    if dy is None and to_float(info.get("trailingAnnualDividendRate")) == 0:
        dy = 0.0
    return {
        "trailingPE": to_float(info.get("trailingPE")),
        "priceToBook": to_float(info.get("priceToBook")),
        "dividendYield": dy,
        "trailingEps": to_float(info.get("trailingEps")),
    }

def build_snapshot(df: pd.DataFrame, fundamentals: Dict[str, Optional[float]]) -> IndicatorSnapshot:
    """Construit un `IndicatorSnapshot` à partir des derniers indicateurs calculés."""
    df_valid = df.dropna()

    if df_valid.empty:
        return IndicatorSnapshot(
            date=None, close=None, sma20=None, sma50=None, sma200=None,
            rsi14=None, macd=None, macd_signal=None, macd_hist=None,
            bb_mid=None, bb_upper=None, bb_lower=None, atr14=None,
            vol=None, vol_sma20=None, fundamentals=fundamentals
        )

    row_idx = df_valid.index[-1]

    def _get(col: str) -> Optional[float]:
        try:
            val = df_valid.loc[row_idx, col]
            if isinstance(val, pd.Series):
                val = val.iloc[0]
            return float(val) if val is not None and pd.notna(val) else None
        except Exception:
            return None

    return IndicatorSnapshot(
        date=row_idx,
        close=_get('Close'),
        sma20=_get('SMA20'),
        sma50=_get('SMA50'),
        sma200=_get('SMA200'),
        rsi14=_get('RSI14'),
        macd=_get('MACD'),
        macd_signal=_get('MACD_signal'),
        macd_hist=_get('MACD_hist'),
        bb_mid=_get('BB_mid'),
        bb_upper=_get('BB_upper'),
        bb_lower=_get('BB_lower'),
        atr14=_get('ATR14'),
        vol=_get('Volume'),
        vol_sma20=_get('VOL_SMA20'),
        fundamentals=fundamentals
    )

# ----------------------- Univers d'actions et noms ----------------------- #
# ~96 valeurs françaises (type SBF 120 : CAC 40 + mid caps), composition ACTUELLE.
# Un backtest sur cette liste subit un biais du survivant (cf. DEC-14).

NOMS_ENTREPRISES = {
        'AC.PA': 'Accor',
        'ADP.PA': 'Aéroports de Paris',
        'AF.PA': 'Air France-KLM',
        'AI.PA': 'Air Liquide',
        'AIR.PA': 'Airbus',
        'ALO.PA': 'Alstom',
        'AMUN.PA': 'Amundi',
        'ARAMI.PA': 'Aramis Group',
        'MT.AS': 'ArcelorMittal',
        'AKE.PA': 'Arkema',
        'ASY.PA': 'Assystem',
        'ATO.PA': 'Atos',
        'CS.PA': 'AXA',
        'BEN.PA': 'Bénéteau',
        'BB.PA': 'Bic',
        'BIM.PA': 'BioMérieux',
        'BNP.PA': 'BNP Paribas',
        'BOL.PA': 'Bolloré',
        'EN.PA': 'Bouygues',
        'BVI.PA': 'Bureau Veritas',
        'CAP.PA': 'Capgemini',
        'CA.PA': 'Carrefour',
        'CLARI.PA': 'Clariane',
        'CDA.PA': 'Compagnie des Alpes',
        'ACA.PA': 'Crédit Agricole',
        'BN.PA': 'Danone',
        'AM.PA': 'Dassault Aviation',
        'DSY.PA': 'Dassault Systèmes',
        'DBG.PA': 'Derichebourg',
        'EDEN.PA': 'Edenred',
        'ELIS.PA': 'Elis',
        'ENGI.PA': 'Engie',
        'ERA.PA': 'Eramet',
        'EL.PA': 'EssilorLuxottica',
        'NAE.PA': 'North Atlantic Energies (Ancien ESSO)',
        'FGR.PA': 'Eiffage',
        'ERF.PA': 'Eurofins Scientific',
        'ENX.PA': 'Euronext',
        'ETL.PA': 'Eutelsat',
        'EXA.PA': 'Exail Technologies',
        'FDE.PA': 'Française de l\'énergie',
        'FDJU.PA': 'Française des Jeux',
        'FNAC.PA': 'Fnac Darty',
        'GET.PA': 'Getlink',
        'GTT.PA': 'GTT',
        'RMS.PA': 'Hermès International',
        'HCO.PA': 'High Co',
        'ITP.PA': 'Interparfums',
        'IPS.PA': 'Ipsos',
        'JCQ.PA': 'Jacquet Metal',
        'DEC.PA': 'JCDecaux',
        'KER.PA': 'Kering',
        'LACR.PA': 'Lacroix',
        'LR.PA': 'Legrand',
        'OR.PA': 'L’Oréal',
        'MC.PA': 'LVMH',
        'MTU.PA': 'Manitou',
        'MEDCL.PA': 'MedinCell',
        'MERY.PA': 'Mercialys',
        'MRN.PA': 'Mersen',
        'ML.PA': 'Michelin',
        'NEX.PA': 'Nexans',
        'NXI.PA': 'Nexity',
        'ORA.PA': 'Orange',
        'OVH.PA': 'OVHcloud',
        'RI.PA': 'Pernod Ricard',
        'VAC.PA': 'Pierre et Vacances',
        'RCO.PA': 'Remy Cointreau',
        'PUB.PA': 'Publicis Groupe',
        'RNO.PA': 'Renault',
        'RUI.PA': 'Rubis',
        'SAF.PA': 'Safran',
        'SGO.PA': 'Saint-Gobain',
        'SAN.PA': 'Sanofi',
        'SU.PA': 'Schneider Electric',
        'SCR.PA': 'Scor',
        'SK.PA': 'SEB',
        'GLE.PA': 'Société Générale',
        'SPIE.PA': 'Spie',
        'SW.PA': 'Sodexo',
        'STLAP.PA': 'Stellantis',
        'STMPA.PA': 'STMicroelectronics',
        'TE.PA': 'Technip Energies',
        'TEP.PA': 'Teleperformance',
        'HO.PA': 'Thales',
        'TTE.PA': 'TotalEnergies',
        'TNG.PA': 'Transgene',
        'UBI.PA': 'Ubisoft',
        'URW.PA': 'Unibail-Rodamco-Westfield',
        'FR.PA': 'Valeo',
        'VK.PA': 'Vallourec',
        'VIE.PA': 'Veolia',
        'VCT.PA': 'Vicat',
        'DG.PA': 'Vinci',
        'VIV.PA': 'Vivendi',
        'WLN.PA': 'Worldline'
}

# ----------------------- Main Routine ----------------------- #

RECOMMENDATION_ORDER = {"ACHAT": 0, "NEUTRE": 1, "VENTE": 2}

def format_recommendation_summary(company_name: str, recommendation: str,
                                  confidence: float, suggested_amount: float,
                                  price: Optional[float] = None) -> str:
    """Formate la ligne de recommandation avec prix et action suggérée."""
    price_text = f" | Prix utilisé: {price:.2f}€" if price is not None else ""
    amount_text = f" | Montant suggéré: €{suggested_amount:.2f}" if suggested_amount > 0 else ""
    return (
        f"{company_name}: {recommendation} | Confiance: {float(confidence):.1%}"
        f"{amount_text}{price_text} | Action suggérée: {recommendation}"
    )

def main():
    """Lance l'analyse complète du CAC40 avec suivi console."""
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

    parser = argparse.ArgumentParser(description="Analyse du CAC40 et recommandation stricte")
    parser.add_argument('--period', type=str, default='5y')
    parser.add_argument('--interval', type=str, default='1d')
    args = parser.parse_args()

    cac40_tickers = list(NOMS_ENTREPRISES.keys())
    results = []
    current_prices = {}

    print(f"\nNOUVELLE VERSION SÉCURISÉE")
    for ticker in cac40_tickers:
        nom_entreprise = NOMS_ENTREPRISES.get(ticker, ticker)
        print(f"\nAnalyse de {nom_entreprise}...")
        df = yf.download(ticker, period=args.period, interval=args.interval, auto_adjust=True, progress=False)
        if df is None or df.empty:
            print(f"Aucune donnée pour {ticker}. Ignoré.")
            continue

        df = flatten_columns(df)
        anomalies = split_anomalies(df, ticker)
        if not anomalies.empty:
            print(f"Saut de cours aberrant le {anomalies[-1].date()} : historique antérieur ignoré (DEC-17)")
        df_ready = prepare_indicators_by_segment(df, anomalies)

        if df_ready is None or df_ready.empty:
            print(f"Pas assez d'historique pour {ticker}. Ignoré.")
            continue

        fundamentals = fetch_fundamentals_safe(ticker)
        snap = build_snapshot(df_ready, fundamentals)
        outcome = compute_score(snap)

        current_prices[ticker] = snap.close
        results.append((ticker, nom_entreprise, outcome, snap))

    # Achats d'abord, puis neutres, puis ventes ; par confiance décroissante dans chaque groupe
    results_sorted = sorted(
        results, key=lambda x: (RECOMMENDATION_ORDER[x[2]["recommendation"]], -x[2]["confidence"])
    )

    for (ticker, nom_entreprise, outcome, snap) in results_sorted:
        print(f"\n{format_recommendation_summary(nom_entreprise, outcome['recommendation'], outcome['confidence'], outcome['suggested_amount'], snap.close)}")
        print("Principaux indicateurs:")
        for r in outcome['reasons']:
            print(f" {r}")

if __name__ == "__main__":
    main()