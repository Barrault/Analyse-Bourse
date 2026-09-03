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
    weights = config.get_section('scoring')
    score = 0
    reasons: List[str] = []

    # Long-term trend: Close > SMA200
    if s.close > s.sma200:
        score += weights['trends']['long_term']
        reasons.append("+ Tendance long terme : Le prix de l'action a augmenté ces derniers mois, montrant que les investisseurs sont confiants.")
    else:
        score -= weights['trends']['long_term']
        reasons.append("- Tendance long terme : Le prix de l'action a baissé ces derniers mois, montrant que les investisseurs sont moins confiants.")

    # Mid-term trend: SMA50 > SMA200
    if s.sma50 > s.sma200:
        score += weights['trends']['mid_term']
        reasons.append("+ Tendance moyen terme : Le prix de l'action a augmenté ces dernières semaines.")
    else:
        score -= weights['trends']['mid_term']
        reasons.append("- Tendance moyen terme : Le prix de l'action stagne ou baisse ces dernières semaines.")

    # Short-term trend: SMA20 > SMA50
    if s.sma20 > s.sma50:
        score += weights['trends']['short_term']
        reasons.append("+ Tendance court terme : Le prix de l'action a augmenté ces derniers jours, montrant un élan récent.")
    else:
        score -= weights['trends']['short_term']
        reasons.append("- Tendance court terme : Le prix de l'action baisse ou stagne ces derniers jours.")

    # Momentum: MACD > 0
    if s.macd > 0:
        score += weights['momentum']['macd_line']
        reasons.append("+ Momentum : Le prix de l'action continue de monter récemment, les acheteurs sont actifs.")
    else:
        score -= weights['momentum']['macd_line']
        reasons.append("- Momentum : Le prix de l'action pourrait ralentir ou baisser, prudence.")

    # MACD Histogram > 0
    if s.macd_hist > 0:
        score += weights['momentum']['macd_histogram']
        reasons.append("+ Accélération : Le mouvement haussier s'accélère, montrant un fort intérêt.")
    else:
        score -= weights['momentum']['macd_histogram']
        reasons.append("- Accélération : Le mouvement haussier ralentit ou le prix baisse.")

    # RSI Analysis
    neutral_lower = config.get('indicators.rsi.neutral_lower')
    neutral_upper = config.get('indicators.rsi.neutral_upper')
    oversold = config.get('indicators.rsi.oversold_threshold')
    overbought = config.get('indicators.rsi.overbought_threshold')

    if neutral_lower <= s.rsi14 <= neutral_upper:
        score += weights['rsi']['neutral_zone']
        reasons.append("* RSI normal : Le prix est équilibré, ni trop acheté ni trop vendu.")
    elif s.rsi14 < oversold:
        score += weights['rsi']['oversold']
        reasons.append("* RSI bas : Le prix a beaucoup baissé, possibilité de rebond.")
    elif s.rsi14 > overbought:
        score += weights['rsi']['overbought']
        reasons.append("- RSI haut : Le prix a beaucoup monté, risque de correction.")

    # Bollinger Bands
    if s.close > s.bb_upper:
        score += weights['bollinger']['above_upper']
        reasons.append("+ Prix élevé récemment : Le prix monte plus que d'habitude, beaucoup d'intérêt des investisseurs.")
    elif s.close < s.bb_lower:
        score += weights['bollinger']['below_lower']
        reasons.append("- Prix bas récemment : Le prix descend plus que d'habitude, possible manque d'intérêt ou ventes fortes.")
    else:
        reasons.append("* Prix normal : Le prix évolue dans sa zone habituelle.")

    # Volume
    if s.vol is not None and s.vol_sma20 is not None:
        if s.vol > s.vol_sma20:
            score += weights['volume']['high_volume']
            reasons.append("+ Volume élevé : Beaucoup d'achats et ventes, le mouvement est soutenu.")
        else:
            score += weights['volume']['low_volume']
            reasons.append("* Volume faible : Peu d'investisseurs bougent, le prix stagne.")

    # Volatility (ATR-based)
    volatility_threshold = config.get('indicators.volatility.threshold', 0.04)
    if s.atr14 / s.close < volatility_threshold:
        score += weights['volatility']['low_volatility']
        reasons.append("+ Volatilité faible : Le prix varie peu, risque limité.")
    else:
        score += weights['volatility']['high_volatility']
        reasons.append("* Volatilité élevée : Le prix peut beaucoup bouger, prudence.")

    tech_score = score

    # ----------------------- Fundamentals ----------------------- #
    pe = s.fundamentals.get("trailingPE")
    pb = s.fundamentals.get("priceToBook")
    dy = s.fundamentals.get("dividendYield")

    weak_fundamentals = False
    toxic_fundamentals = False

    roe = None
    if pe is not None and pb is not None and pe > 0:
        roe = 1 / pe * pb * 100

    # --- PE analysis ---
    if pe is not None:
        if pe < 0:
            toxic_fundamentals = True
            reasons.append(f"-- PE négatif (PE={pe:.1f}) : L'entreprise essuie des pertes nettes. Profil fondamental très dégradé.")
        elif 0 <= pe < 8:
            score += weights['fundamentals']['pe']['very_low']
            reasons.append(f"- PE très bas (PE={pe:.1f}) : Le PE montre combien vous payez pour chaque euro de profit annuel. Un PE très bas (< 8) peut signifier une opportunité ou un piège.")
        elif 8 <= pe <= 14:
            if s.close > s.sma200 and s.macd > 0:
                score += weights['fundamentals']['pe']['low']
                reasons.append(f"+ PE raisonnable (PE={pe:.1f}, c'est-à-dire {pe:.1f}€ dépensé par euro de profit) : Entre 8 et 14, c'est un bon rapport qualité/prix, surtout avec une tendance haussière.")
            else:
                score += weights['fundamentals']['pe']['low_weak']
                reasons.append(f"- PE correct (PE={pe:.1f}) mais la dynamique est faible - pas assez de raisons d'acheter.")
        elif 14 < pe <= 22:
            score += weights['fundamentals']['pe']['moderate']
            reasons.append(f"- PE déjà exigeant (PE={pe:.1f}) : Entre 14 et 22, vous payez davantage par euro de profit, sans forte croissance visible.")
            weak_fundamentals = True
        elif pe > 22:
            score += weights['fundamentals']['pe']['high']
            reasons.append(f"-- PE élevé (PE={pe:.1f}) : Au-dessus de 22, c'est cher. Le prix devrait augmenter vite pour justifier cette valorisation.")
            weak_fundamentals = True

    # --- Continuous value scoring ---
    fund_weights = weights['fundamentals']
    pe_scale = config.get('scoring.fundamentals.pe_scale', 25.0)
    pb_scale = config.get('scoring.fundamentals.pb_scale', 3.0)
    roe_threshold = config.get('scoring.fundamentals.roe_threshold', 10.0)
    pe_cont_weight = fund_weights.get('pe_continuous_weight', 1.4)
    pb_cont_weight = fund_weights.get('pb_continuous_weight', 1.4)
    roe_weight = fund_weights.get('roe_weight', 0.6)
    value_conf_weight = fund_weights.get('value_confirmation', 1.5)

    if pe is not None and pe > 0:
        pe_score = max(0.0, 1.0 - (pe / pe_scale))
        score += pe_cont_weight * pe_score
        if pe_score > 0.6:
            reasons.append(f"+ Valorisation PE favorable (PE={pe:.1f}) : le titre est relativement peu cher au regard de ses profits.")
        elif pe_score < 0.3:
            reasons.append(f"- Valorisation PE chère (PE={pe:.1f}) : le titre est relativement cher au regard de ses profits.")

    if pb is not None:
        pb_score = max(0.0, 1.0 - (pb / pb_scale))
        score += pb_cont_weight * pb_score
        if pb_score > 0.6:
            reasons.append(f"+ Valorisation P/B favorable (P/B={pb:.1f}) : le titre est peu cher par rapport à ses actifs.")
        elif pb_score < 0.3:
            reasons.append(f"- Valorisation P/B chère (P/B={pb:.1f}) : le titre est cher par rapport à ses actifs.")

    if roe is not None:
        if roe >= 12:
            score += roe_weight
            reasons.append(f"+ ROE implicite solide (ROE≈{roe:.1f}%) : la société transforme bien ses fonds propres en profit.")
        elif roe >= roe_threshold:
            score += roe_weight * 0.5
        else:
            score -= roe_weight * 0.5

    # --- Price to Book analysis ---
    if pb is not None:
        if pb < 1:
            if roe is not None and roe > 10:
                score += weights['fundamentals']['pb']['very_low_good_roe']
                reasons.append(f"+ P/B sous-évalué (P/B={pb:.1f}) avec bon ROE (ROE≈{roe:.1f}%) : Un P/B < 1 signifie vous l'achetez moins cher que sa valeur en actifs.")
            else:
                score += weights['fundamentals']['pb']['very_low_bad_roe']
                reasons.append(f"- P/B bas (P/B={pb:.1f}) mais rentabilité faible : Peut-être bon marché pour une raison (mauvaise gestion).")
                weak_fundamentals = True
        elif 1 <= pb <= 2.5:
            if roe is not None and roe >= 12:
                score += weights['fundamentals']['pb']['moderate_good_roe']
                reasons.append(f"+ P/B normal (P/B={pb:.1f}, prix comparé à la valeur de l'entreprise) et bonne rentabilité (ROE≥12%, c'est-à-dire ≥12% de profit sur les fonds propres) : Prix et valeur en actifs sont équilibrés, l'entreprise génère de bons profits.")
            else:
                score += weights['fundamentals']['pb']['moderate_bad_roe']
                reasons.append(f"- P/B correct (P/B={pb:.1f}) mais rentabilité insuffisante (ROE faible).")
                weak_fundamentals = True
        elif pb > 2.5:
            score += weights['fundamentals']['pb']['high']
            reasons.append(f"- P/B élevé (P/B={pb:.1f}) : Risqué sauf si forte croissance attendue.")
            weak_fundamentals = True
            toxic_fundamentals = True

    # --- Cross PE & PB (sanity check) ---
    if pe is not None and pb is not None:
        if pe > 20 and pb > 3:
            score += weights['fundamentals']['expensive_both']
            reasons.append(f"-- Double surévaluation : PE élevé (PE={pe:.1f}, cher par euro de profit) + P/B élevé (P/B={pb:.1f}, cher par rapport aux actifs). Risque très élevé.")
        if pe < 12 and pb < 1.2 and s.close > s.sma200:
            score += value_conf_weight
            reasons.append(f"+ Décote cohérente confirmée : PE bas (PE={pe:.1f}) + P/B bas (P/B={pb:.1f}) + prix en hausse.")

    fund_score = score - tech_score

    # --- Dividend ---
    if dy is not None:
        if dy >= 5:
            score += weights['fundamentals']['dividend']['high_yield']
            reasons.append(f"+ Dividende élevé et défensif ({dy:.1f}%).")
        elif 2 <= dy < 5:
            reasons.append(f"* Dividende correct mais non protecteur ({dy:.1f}%).")
        elif dy == 0:
            score += weights['fundamentals']['dividend']['no_dividend']
            reasons.append("- Aucun dividende : Aucune protection en cas de baisse.")

    thresholds = config.get('scoring.thresholds')
    if score >= thresholds['buy']:
        rec = "ACHAT"
    elif score <= thresholds['sell']:
        rec = "VENTE"
    else:
        rec = "NEUTRE"

    buy_threshold = thresholds['buy']
    sell_threshold = thresholds['sell']

    if rec == "ACHAT":
        confidence = min((score - buy_threshold) / max(abs(buy_threshold), 1) + 0.5, 1.0)
        if weak_fundamentals or toxic_fundamentals:
            confidence = min(confidence, 0.40)
            reasons.append("- Pénalité de confiance : Achat dégradé en profil spéculatif/technique. Les fondamentaux n'appuient pas la hausse des prix.")

    elif rec == "VENTE":
        confidence = min((sell_threshold - score) / max(abs(sell_threshold), 1) + 0.5, 1.0)

        # 1. CAS TOXIQUE : Fondamentaux désastreux (Pertes nettes ou bulle sur les actifs)
        if toxic_fundamentals:
            confidence = max(confidence, 0.90)
            reasons.append("+ Vente de conviction : La chute technique est confirmée par des fondamentaux toxiques ou une surévaluation critique.")

        # 2. CAS VALUE SUPPORT : Le titre baisse mais il est déjà tellement donné qu'on ne shorte pas à 100%
        elif pe is not None and 0 < pe < 11 and pb is not None and pb < 1.1:
            confidence = min(confidence, 0.35)
            reasons.append("- Alerte Value Support : Les indicateurs techniques sont baissiers, mais l'action est fondamentalement très bon marché (PE et P/B bas). Confiance bridée pour éviter de vendre au plus bas.")

        # 3. CAS PANIC SELL : Excellents fondamentaux, le marché jette le bébé avec l'eau du bain
        elif not weak_fundamentals:
            confidence = min(confidence, 0.30)
            reasons.append("- Alerte Panic Sell : Les indicateurs techniques virent au rouge, mais la qualité fondamentale de l'entreprise reste excellente. Vente à forte conviction injustifiée.")
    else:
        mid = (buy_threshold + sell_threshold) / 2
        spread = max(buy_threshold - sell_threshold, 1)
        confidence = min(abs(score - mid) / spread, 1.0)

    confidence = max(confidence, 0.0)
    suggested_amount = round(confidence * 1000, 2)

    return {
        "score": score,
        "recommendation": rec,
        "confidence": round(confidence, 2),
        "suggested_amount": suggested_amount,
        "reasons": reasons
    }

# ----------------------- Fundamentals & Snapshot ----------------------- #

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
        if dy is not None and dy < 1:
            dy *= 100
        return {"trailingPE": pe, "priceToBook": pb, "dividendYield": dy}
    except Exception:
        return {"trailingPE": None, "priceToBook": None, "dividendYield": None}

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
        'ARRJ.F': 'ArcelorMittal',
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
        'ELIS.PA': 'Elis',
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

def format_recommendation_summary(company_name: str, recommendation: str,
                                  confidence: float, suggested_amount: float,
                                  price: Optional[float] = None) -> str:
    """Formate la ligne de recommandation avec prix et action suggérée."""
    price_text = f" | Prix utilisé: {price:.2f}€" if price is not None else ""
    return (
        f"{company_name}: {recommendation} | Confiance: {round(float(confidence), 2)} "
        f"| Montant suggéré: €{suggested_amount:.2f}{price_text} | Action suggérée: {recommendation}"
    )

def main():
    """Lance l'analyse complète du CAC40 avec suivi console."""
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

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

        df_ready = prepare_indicators(df)

        if df_ready is None or df_ready.empty:
            print(f"Pas assez d'historique pour {ticker}. Ignoré.")
            continue

        fundamentals = fetch_fundamentals_safe(ticker)
        snap = build_snapshot(df_ready, fundamentals)
        outcome = compute_score(snap)

        current_prices[ticker] = snap.close
        results.append((ticker, nom_entreprise, outcome, snap))

    results_sorted = sorted(results, key=lambda x: x[2]["confidence"], reverse=True)

    for (ticker, nom_entreprise, outcome, snap) in results_sorted:
        print(f"\n{format_recommendation_summary(nom_entreprise, outcome['recommendation'], outcome['confidence'], outcome['suggested_amount'], snap.close)}")
        print("Principaux indicateurs:")
        for r in outcome['reasons']:
            print(f" {r}")

if __name__ == "__main__":
    main()