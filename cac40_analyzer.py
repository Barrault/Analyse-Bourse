"""
CAC40 Stock Analyzer - Version stricte
"""
# -*- coding: utf-8 -*-
import argparse
from datetime import date
import numpy as np
import pandas as pd
import yfinance as yf
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
import ta
import sys
import io

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
# ----------------------- Indicator Preparation ----------------------- #

def prepare_indicators(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """Prépare les indicateurs techniques pour un DataFrame."""
    if df is None or df.empty:
        return None

    df = df.copy()

    # Si le DataFrame a un MultiIndex (yfinance avec plusieurs tickers), aplatir
    if isinstance(df.columns, pd.MultiIndex) or getattr(df.columns, 'nlevels', 1) > 1:
        required_cols = ['Close', 'High', 'Low', 'Volume', 'Adj Close', 'Open']
        chosen = None
        for lvl in range(df.columns.nlevels):
            vals = df.columns.get_level_values(lvl)
            if any(v in vals for v in required_cols):
                chosen = vals
                break

        if chosen is not None:
            df.columns = chosen
        else:
            df.columns = df.columns.get_level_values(-1)

    # S'assurer que Close, High, Low, Volume existent
    required_cols = ['Close', 'High', 'Low', 'Volume']
    for col in required_cols:
        if col not in df.columns:
            return None

    # Charger les paramètres depuis la configuration
    sma_params = config.get_section('indicators')['sma']
    rsi_params = config.get_section('indicators')['rsi']
    bb_params = config.get_section('indicators')['bollinger']
    atr_params = config.get_section('indicators')['atr']
    vol_params = config.get_section('indicators')['volume']

    # Calculer les indicateurs avec les paramètres de config
    df['SMA20'] = sma(df['Close'], sma_params['short_window'])
    df['SMA50'] = sma(df['Close'], sma_params['mid_window'])
    df['SMA200'] = sma(df['Close'], sma_params['long_window'])
    df['RSI14'] = rsi(df['Close'], rsi_params['window'])

    macd_line, signal_line, hist = macd(df['Close'])
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
    Évalue les tendances, momentum, RSI, bandes de Bollinger, volume, volatilité
    et fondamentaux pour produire un score, une recommandation et un niveau de confiance.
    """
    # Charger les poids depuis la configuration
    weights = config.get_section('scoring')

    score = 0
    reasons: List[str] = []

    # Long-term trend: Close > SMA200
    if s.close > s.sma200:
        score += weights['trends']['long_term']
        reasons.append("+ Tendance long terme : le prix monte depuis plusieurs mois, le marché est confiant.")
    else:
        score -= weights['trends']['long_term']
        reasons.append("- Tendance long terme : le prix baisse depuis plusieurs mois, le marché est moins confiant.")

    # Mid-term trend: SMA50 > SMA200
    if s.sma50 > s.sma200:
        score += weights['trends']['mid_term']
        reasons.append("+ Tendance moyen terme : le prix est en hausse depuis plusieurs semaines.")
    else:
        score -= weights['trends']['mid_term']
        reasons.append("- Tendance moyen terme : le prix stagne ou baisse depuis plusieurs semaines")

    # Short-term trend: SMA20 > SMA50
    if s.sma20 > s.sma50:
        score += weights['trends']['short_term']
        reasons.append("+ Tendance court terme : le prix monte depuis quelques jours, signe d'élan récent.")
    else:
        score -= weights['trends']['short_term']
        reasons.append("- Tendance court terme : le prix baisse ou stagne depuis quelques jours.")

    # Momentum: MACD > 0
    if s.macd > 0:
        score += weights['momentum']['macd_line']
        reasons.append("+ Momentum : le prix continue de monter récemment, les acheteurs sont actifs.")
    else:
        score -= weights['momentum']['macd_line']
        reasons.append("- Momentum : le prix pourrait ralentir ou baisser, prudence.")

    # MACD Histogram > 0
    if s.macd_hist > 0:
        score += weights['momentum']['macd_histogram']
        reasons.append("+ Accélération : le mouvement haussier s'intensifie, signe d'intérêt fort.")
    else:
        score -= weights['momentum']['macd_histogram']
        reasons.append("- Accélération : le mouvement haussier ralentit ou le prix descend.")

    # RSI Analysis
    neutral_lower = config.get('indicators.rsi.neutral_lower')
    neutral_upper = config.get('indicators.rsi.neutral_upper')
    oversold = config.get('indicators.rsi.oversold_threshold')
    overbought = config.get('indicators.rsi.overbought_threshold')

    if neutral_lower <= s.rsi14 <= neutral_upper:
        score += weights['rsi']['neutral_zone']
        reasons.append("* RSI normal : le prix est équilibré, ni trop acheté ni trop vendu")
    elif s.rsi14 < oversold:
        score += weights['rsi']['oversold']
        reasons.append("* RSI bas : le prix a beaucoup baissé, possibilité de rebond.")
    elif s.rsi14 > overbought:
        score -= weights['rsi']['overbought']
        reasons.append("- RSI haut : le prix a beaucoup monté, risque de correction")

    # Bollinger Bands
    if s.close > s.bb_upper:
        score += weights['bollinger']['above_upper']
        reasons.append("+ Prix élevé récemment : le prix monte plus que d'habitude, beaucoup d'intérêt des investisseurs.")
    elif s.close < s.bb_lower:
        score -= weights['bollinger']['below_lower']
        reasons.append("- Prix bas récemment : le prix descend plus que d'habitude, possible désintérêt ou ventes fortes.")
    else:
        reasons.append("* Prix normal : le prix évolue dans sa zone habituelle.")

    # Volume
    if s.vol is not None and s.vol_sma20 is not None:
        if s.vol > s.vol_sma20:
            score += weights['volume']['high_volume']
            reasons.append("+ Volume élevé : beaucoup d'achats et ventes, le mouvement est soutenu.")
        else:
            score -= weights['volume']['low_volume']
            reasons.append("* Volume faible : peu d'investisseurs bougent, le prix stagne")

    # Volatility (ATR-based)
    volatility_threshold = config.get('indicators.volatility.threshold', 0.04)
    if s.atr14 / s.close < volatility_threshold:
        score += weights['volatility']['low_volatility']
        reasons.append("+ Volatilité faible : le prix varie peu, risque limité.")
    else:
        score -= weights['volatility']['high_volatility']
        reasons.append("* Volatilité élevée : le prix peut beaucoup bouger, prudence.")

    # ----------------------- Fundamentals (strict & punitive) ----------------------- #
    pe = s.fundamentals.get("trailingPE")
    pb = s.fundamentals.get("priceToBook")
    dy = s.fundamentals.get("dividendYield")

    # Helpers dérivés (qualité)
    roe = None
    if pe is not None and pb is not None and pe > 0:
        roe = 1 / pe * pb * 100  # approximation ROE implicite (%)

    # --- PE analysis (croisé avec tendance & momentum) ---
    if pe is not None:
        if pe < 8:
            score -= weights['fundamentals']['pe']['very_low']
            reasons.append(f"- PE très bas (PE={pe:.1f}) : possible value trap.")
        elif 8 <= pe <= 14:
            if s.close > s.sma200 and s.macd > 0:
                score += weights['fundamentals']['pe']['low']
                reasons.append(f"+ PE raisonnable et marché haussier (PE={pe:.1f}).")
            else:
                score -= weights['fundamentals']['pe']['low_weak']
                reasons.append(f"- PE correct mais dynamique faible (PE={pe:.1f}).")
        elif 14 < pe <= 22:
            score -= weights['fundamentals']['pe']['moderate']
            reasons.append(f"- PE déjà exigeant sans forte croissance visible (PE={pe:.1f}).")
        elif pe > 22:
            score -= weights['fundamentals']['pe']['high']
            reasons.append(f"-- PE élevé et risque de surévaluation (PE={pe:.1f}).")

    # --- Price to Book analysis (croisé avec ROE implicite) ---
    if pb is not None:
        if pb < 1:
            if roe is not None and roe > 10:
                score += weights['fundamentals']['pb']['very_low_good_roe']
                reasons.append(f"+ P/B décoté avec ROE correct (P/B={pb:.1f}, ROE≈{roe:.1f}%).")
            else:
                score -= weights['fundamentals']['pb']['very_low_bad_roe']
                reasons.append(f"- P/B bas mais rentabilité faible (P/B={pb:.1f}).")
        elif 1 <= pb <= 2.5:
            if roe is not None and roe >= 12:
                score += weights['fundamentals']['pb']['moderate_good_roe']
                reasons.append(f"+ P/B raisonnable et bonne rentabilité (P/B={pb:.1f}).")
            else:
                score -= weights['fundamentals']['pb']['moderate_bad_roe']
                reasons.append(f"- P/B correct mais ROE insuffisant (P/B={pb:.1f}).")
        elif pb > 2.5:
            score -= weights['fundamentals']['pb']['high']
            reasons.append(f"- P/B élevé : forte prime sur les actifs (P/B={pb:.1f}).")

    # --- Cross PE & PB (sanity check) ---
    if pe is not None and pb is not None:
        if pe > 20 and pb > 3:
            score -= weights['fundamentals']['expensive_both']
            reasons.append("-- Double surévaluation PE + P/B : risque asymétrique.")
        if pe < 12 and pb < 1.2 and s.close > s.sma200:
            score += weights['fundamentals']['cheap_with_growth']
            reasons.append("+ Décote cohérente confirmée par le marché.")

    # --- Dividend (defensive bias) ---
    if dy is not None:
        if dy >= 5:
            score += weights['fundamentals']['dividend']['high_yield']
            reasons.append(f"+ Dividende élevé et défensif ({dy:.1f}%).")
        elif 2 <= dy < 5:
            reasons.append(f"* Dividende correct mais non protecteur ({dy:.1f}%).")
        elif dy == 0:
            score -= weights['fundamentals']['dividend']['no_dividend']
            reasons.append("- Aucun dividende : aucune protection en cas de baisse.")

    # Recommendation - using thresholds from config
    thresholds = config.get('scoring.thresholds')
    if score >= thresholds['buy']:
        rec = "ACHAT"
    elif score <= thresholds['sell']:
        rec = "VENTE"
    else:
        rec = "NEUTRE"

    confidence = min(max(abs(score)/10, 0), 1.0)

    # Retourne un dictionnaire avec score, recommandation, confiance et explications
    return {
        "score": score,
        "recommendation": rec,
        "confidence": round(confidence, 2),
        "reasons": reasons
    }

    # Retourne un dictionnaire avec score, recommandation, confiance et explications

    return {
        "score": score,
        "recommendation": rec,
        "confidence": round(confidence, 2),
        "reasons": reasons
    }

# ----------------------- Fundamentals & Snapshot ----------------------- #
# Récupération des fondamentaux (PE, P/B, dividende) et création d’un snapshot


def fetch_fundamentals_safe(ticker: str) -> Dict[str, Optional[float]]:
    """Récupère les fondamentaux d’un ticker Yahoo Finance, avec conversion sécurisée."""
    def to_float(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return None

    try:
        info = yf.Ticker(ticker).info
        pe = to_float(info.get("trailingPE"))
        pb = to_float(info.get("priceToBook"))
        dy = to_float(info.get("dividendYield"))
        # Si Yahoo renvoie un ratio de dividende (ex: 0.023), convertir en pourcentage :
        if dy is not None and dy < 1:
            dy *= 100
        return {"trailingPE": pe, "priceToBook": pb, "dividendYield": dy}
    except Exception:
        return {"trailingPE": None, "priceToBook": None, "dividendYield": None}


def build_snapshot(df: pd.DataFrame, fundamentals: Dict[str, Optional[float]]) -> IndicatorSnapshot:
    """Construit un `IndicatorSnapshot` à partir des derniers indicateurs calculés."""
    # Trouver la DERNIÈRE LIGNE SANS NaN (tous les indicateurs valides)
    df_valid = df.dropna()

    if df_valid.empty:
        # Si aucune ligne valide, retourner un snapshot vide
        snap = IndicatorSnapshot(
            date=None,
            close=None,
            sma20=None,
            sma50=None,
            sma200=None,
            rsi14=None,
            macd=None,
            macd_signal=None,
            macd_hist=None,
            bb_mid=None,
            bb_upper=None,
            bb_lower=None,
            atr14=None,
            vol=None,
            vol_sma20=None,
            fundamentals=fundamentals
        )
        return snap

    # Accéder à la dernière ligne comme un scalar
    row_idx = df_valid.index[-1]

    def _get(col: str) -> Optional[float]:
        try:
            val = df_valid.loc[row_idx, col]
            # Si c'est une Series (MultiIndex), prendre le premier élément
            if isinstance(val, pd.Series):
                val = val.iloc[0]
            return float(val) if val is not None and pd.notna(val) else None
        except Exception:
            return None

    snap = IndicatorSnapshot(
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

    return snap


# ----------------------- Tickers CAC40 et noms ----------------------- #

NOMS_ENTREPRISES = {
        'AC.PA': 'Accor',
        'ADP.PA': 'Aéroports de Paris',
        'AF.PA': 'Air France-KLM',
        'AI.PA': 'Air Liquide',
        'AIR.PA': 'Airbus',
        'ALO.PA': 'Alstom',
        'AMUN.PA': 'Amundi',
        'ARAMI.PA': 'Aramis Group',
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
        'ES.PA': 'Esso',
        'EXA.PA': 'Exail Technologies',
        'ERF.PA': 'Eurofins Scientific',
        'ENX.PA': 'Euronext',
        'ETL.PA': 'Eutelsat',
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
# Point d'entrée : analyse toutes les valeurs du CAC40, calcule les indicateurs,
# affiche les recommandations et met à jour les fichiers Excel.

def main():
    """Lance l'analyse complète du CAC40 avec suivi console et simulation de trades."""
    # Forcer UTF-8 sur Windows
    if sys.stdout.encoding.lower() != 'utf-8':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    parser = argparse.ArgumentParser(description="Analyse du CAC40 et recommandation stricte")
    parser.add_argument('--period', type=str, default='5y')
    parser.add_argument('--interval', type=str, default='1d')
    args = parser.parse_args()

    cac40_tickers = list(NOMS_ENTREPRISES.keys())
    results = []

    # We will gather current prices to initialize positions if needed
    current_prices = {}

    for ticker in cac40_tickers:
        nom_entreprise = NOMS_ENTREPRISES.get(ticker, ticker)
        print(f"\nAnalyse de {nom_entreprise}...")
        df = yf.download(ticker, period=args.period, interval=args.interval, auto_adjust=True, progress=False)
        if df is None or df.empty:
            print(f"Aucune donnée pour {ticker}. Ignoré.")
            continue

        df['SMA20'] = sma(df['Close'], 20)
        df['SMA50'] = sma(df['Close'], 50)
        df['SMA200'] = sma(df['Close'], 200)
        df['RSI14'] = rsi(df['Close'], 14)
        macd_line, signal_line, hist = macd(df['Close'])
        df['MACD'] = macd_line
        df['MACD_signal'] = signal_line
        df['MACD_hist'] = hist
        bb_mid, bb_upper, bb_lower = bollinger(df['Close'], 20, 2.0)
        df['BB_mid'] = bb_mid
        df['BB_upper'] = bb_upper
        df['BB_lower'] = bb_lower
        df['ATR14'] = atr(df['High'], df['Low'], df['Close'], 14)
        df['VOL_SMA20'] = sma(df['Volume'], 20)

        fundamentals = fetch_fundamentals_safe(ticker)
        df_ready = df.dropna().copy()
        if df_ready.empty:
            print(f"Pas assez d'historique pour {ticker}. Ignoré.")
            continue

        snap = build_snapshot(df_ready, fundamentals)
        outcome = compute_score(snap)

        # Recalculer recommendation et confidence après score macro
        total_score = outcome["score"]
        if total_score >= 3:
            outcome["recommendation"] = "ACHAT"
        elif total_score <= -3:
            outcome["recommendation"] = "VENTE"
        else:
            outcome["recommendation"] = "NEUTRE"
        outcome["confidence"] = min(max(abs(total_score)/10, 0), 1.0)

        # keep current price for initialization and trades
        current_prices[ticker] = snap.close

        results.append((ticker, nom_entreprise, outcome, snap))

    # Sort results by confidence descending (as requested)
    results_sorted = sorted(results, key=lambda x: x[2]["confidence"], reverse=True)

    for (ticker, nom_entreprise, outcome, snap) in results_sorted:
        print(f"\n{nom_entreprise}: {outcome['recommendation']} | {round(outcome['confidence'], 2)}")
        print("Principaux indicateurs:")
        for r in outcome['reasons']:
            print(f" {r}")

if __name__ == "__main__":
    main()
