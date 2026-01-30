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
    score = 0
    reasons: List[str] = []

    # Analyse des tendances long, moyen et court terme
    # ... (commentaires détaillés laissés dans ton code pour clarté)
    # Momentum, RSI, bandes de Bollinger, volume et volatilité
    # Analyse des ratios fondamentaux (PE, P/B, dividende)
    # Détermination de la recommandation finale (ACHAT, VENTE, NEUTRE)

    # Long-term trend
    if s.close > s.sma200:
        score += 2   # réduit de +2 à +1
        reasons.append("+ Tendance long terme : le prix monte depuis plusieurs mois, le marché est confiant.")
    else:
        score -= 2   # amplifié de -2 à -2 (inchangé)
        reasons.append("- Tendance long terme : le prix baisse depuis plusieurs mois, le marché est moins confiant.")

    # Mid-term trend
    if s.sma50 > s.sma200:
        score += 1.2  # réduit de +1 à +0.5
        reasons.append("+ Tendance moyen terme : le prix est en hausse depuis plusieurs semaines.")
    else:
        score -= 1.2    # amplifié de -1 à -2
        reasons.append("- Tendance moyen terme : le prix stagne ou baisse depuis plusieurs semaines")

    # Short-term trend
    if s.sma20 > s.sma50:
        score += 1  # réduit de +1 à +0.5
        reasons.append("+ Tendance court terme : le prix monte depuis quelques jours, signe d'élan récent.")
    else:
        score -= 1  # amplifié de -1 à -1.5
        reasons.append("- Tendance court terme : le prix baisse ou stagne depuis quelques jours.")

    # Momentum
    if s.macd > 0:
        score += 1.8  # réduit de +1 à +0.5
        reasons.append("+ Momentum : le prix continue de monter récemment, les acheteurs sont actifs.")
    else:
        score -= 1.8  # amplifié de -1 à -1.5
        reasons.append("- Momentum : le prix pourrait ralentir ou baisser, prudence.")

    if s.macd_hist > 0:
        score += 1.5  # réduit de +1 à +0.5
        reasons.append("+ Accélération : le mouvement haussier s'intensifie, signe d'intérêt fort.")
    else:
        score -= 1.5  # amplifié de -1 à -1.5
        reasons.append("- Accélération : le mouvement haussier ralentit ou le prix descend.")

    # RSI
    if 50 <= s.rsi14 <= 70:
        score += 0.5  # réduit
        reasons.append("* RSI normal : le prix est équilibré, ni trop acheté ni trop vendu")
    elif s.rsi14 < 30:
        score += 1  # pénalise légèrement plus
        reasons.append("* RSI bas : le prix a beaucoup baissé, possibilité de rebond.")
    elif s.rsi14 > 70:
        score -= 1.5  # amplifié
        reasons.append("- RSI haut : le prix a beaucoup monté, risque de correction")

    # Bollinger Bands
    if s.close > s.bb_upper:
        score += 0.8  # réduit
        reasons.append("+ Prix élevé récemment : le prix monte plus que d'habitude, beaucoup d'intérêt des investisseurs.")
    elif s.close < s.bb_lower:
        score -= 1.5  # amplifié
        reasons.append("- Prix bas récemment : le prix descend plus que d'habitude, possible désintérêt ou ventes fortes.")
    else:
        reasons.append("* Prix normal : le prix évolue dans sa zone habituelle.")

    # Volume
    if s.vol is not None and s.vol_sma20 is not None:
        if s.vol > s.vol_sma20:
            score += 0.5  # réduit
            reasons.append("+ Volume élevé : beaucoup d'achats et ventes, le mouvement est soutenu.")
        else:
            score -= 0.5  # pénalise un peu le volume faible
            reasons.append("* Volume faible : peu d'investisseurs bougent, le prix stagne")

    # Volatility
    if s.atr14 / s.close < 0.04:
        score += 0.8  # réduit
        reasons.append("+ Volatilité faible : le prix varie peu, risque limité.")
    else:
        score -= 0.8  # amplifié légèrement
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
            # très bas = soit opportunité, soit gros problème → on reste méfiant
            score -= 0.5
            reasons.append(f"- PE très bas (PE={pe:.1f}) : possible value trap.")
        elif 8 <= pe <= 14:
            if s.close > s.sma200 and s.macd > 0:
                score += 0.8
                reasons.append(f"+ PE raisonnable et marché haussier (PE={pe:.1f}).")
            else:
                score -= 0.5
                reasons.append(f"- PE correct mais dynamique faible (PE={pe:.1f}).")
        elif 14 < pe <= 22:
            score -= 0.5
            reasons.append(f"- PE déjà exigeant sans forte croissance visible (PE={pe:.1f}).")
        elif pe > 22:
            score -= 2
            reasons.append(f"-- PE élevé et risque de surévaluation (PE={pe:.1f}).")

    # --- Price to Book analysis (croisé avec ROE implicite) ---
    if pb is not None:
        if pb < 1:
            if roe is not None and roe > 10:
                score += 0.5
                reasons.append(f"+ P/B décoté avec ROE correct (P/B={pb:.1f}, ROE≈{roe:.1f}%).")
            else:
                score -= 1
                reasons.append(f"- P/B bas mais rentabilité faible (P/B={pb:.1f}).")
        elif 1 <= pb <= 2.5:
            if roe is not None and roe >= 12:
                score += 0.5
                reasons.append(f"+ P/B raisonnable et bonne rentabilité (P/B={pb:.1f}).")
            else:
                score -= 0.5
                reasons.append(f"- P/B correct mais ROE insuffisant (P/B={pb:.1f}).")
        elif pb > 2.5:
            score -= 1.5
            reasons.append(f"- P/B élevé : forte prime sur les actifs (P/B={pb:.1f}).")

    # --- Cross PE & PB (sanity check) ---
    if pe is not None and pb is not None:
        if pe > 20 and pb > 3:
            score -= 1.5
            reasons.append("-- Double surévaluation PE + P/B : risque asymétrique.")
        if pe < 12 and pb < 1.2 and s.close > s.sma200:
            score += 0.5
            reasons.append("+ Décote cohérente confirmée par le marché.")

    # --- Dividend (defensive bias) ---
    if dy is not None:
        if dy >= 5:
            score += 0.8
            reasons.append(f"+ Dividende élevé et défensif ({dy:.1f}%).")
        elif 2 <= dy < 5:
            reasons.append(f"* Dividende correct mais non protecteur ({dy:.1f}%).")
        elif dy == 0:
            score -= 1
            reasons.append("- Aucun dividende : aucune protection en cas de baisse.")

    # Recommendation
    if score >= 5:
        rec = "ACHAT"
    elif score <= -3:
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
    last = df.iloc[-1]
    # helper pour convertir proprement en float
    def _f(x): return float(x) if not hasattr(x, "iloc") else float(x.iloc[0])
    snap = IndicatorSnapshot(
        date=last.name,
        close=_f(last['Close']),
        sma20=_f(last['SMA20']),
        sma50=_f(last['SMA50']),
        sma200=_f(last['SMA200']),
        rsi14=_f(last['RSI14']),
        macd=_f(last['MACD']),
        macd_signal=_f(last['MACD_signal']),
        macd_hist=_f(last['MACD_hist']),
        bb_mid=_f(last['BB_mid']),
        bb_upper=_f(last['BB_upper']),
        bb_lower=_f(last['BB_lower']),
        atr14=_f(last['ATR14']),
        vol=_f(last['Volume']),
        vol_sma20=_f(last['VOL_SMA20']),
        fundamentals=fundamentals
    )
    return snap


# ----------------------- Main Routine ----------------------- #
# Point d’entrée : analyse toutes les valeurs du CAC40, calcule les indicateurs,
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
