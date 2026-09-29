"""
Backtester pour CAC40 Analyzer
Simule les trades réels avec frais Bourse Direct 2024-2026
"""
# -*- coding: utf-8 -*-
import math
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import yfinance as yf

from cac40_analyzer import (
    compute_score, fetch_fundamentals_safe, flatten_columns, order_amount,
    build_snapshot, prepare_indicators_by_segment, split_anomalies, NOMS_ENTREPRISES
)
from config_loader import config

# ----------------------- Frais Bourse Direct ----------------------- #

def calculate_fees(amount: float) -> float:
    """Calcule les frais Bourse Direct pour un montant donné, selon la configuration."""
    fee_structure = config.get('fees.structure')

    for fee_tier in fee_structure:
        max_amount = fee_tier.get('max_amount')

        # Dernier tier avec max_amount = None
        if max_amount is None:
            percentage_fee = fee_tier['percentage_fee']
            return amount * percentage_fee

        # Tier avec montant maximum
        if amount <= max_amount:
            return fee_tier['fixed_fee']

    raise ValueError("fees.structure doit se terminer par un palier 'max_amount: null'")

# Fréquences de rebalance (config trading.rebalance.frequency) -> périodes pandas
REBALANCE_FREQUENCIES = {"week": "W", "month": "M", "quarter": "Q"}

TRADING_DAYS_PER_YEAR = 252

def performance_metrics(equity: pd.Series) -> Dict[str, float]:
    """Indicateurs de performance d'une courbe de valeur journalière (cf. DEC-13).

    Sharpe calculé avec un taux sans risque nul : il sert à COMPARER la stratégie au
    benchmark sur la même période, pas à produire une valeur absolue.
    """
    equity = equity.dropna()
    daily_returns = equity.pct_change().dropna()
    years = max((equity.index[-1] - equity.index[0]).days / 365.25, 1 / 365.25)
    total_return = equity.iloc[-1] / equity.iloc[0] - 1
    volatility = daily_returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR) if len(daily_returns) > 1 else 0.0
    annual_mean = daily_returns.mean() * TRADING_DAYS_PER_YEAR if len(daily_returns) else 0.0
    drawdown = equity / equity.cummax() - 1
    return {
        "total_return_pct": total_return * 100,
        "cagr_pct": ((1 + total_return) ** (1 / years) - 1) * 100,
        "volatility_pct": volatility * 100,
        "sharpe": annual_mean / volatility if volatility > 0 else 0.0,
        "max_drawdown_pct": drawdown.min() * 100,
    }

# ----------------------- Portfolio & Trade Tracking ----------------------- #

@dataclass
class Trade:
    """Enregistre un trade (achat ou vente)."""
    date: pd.Timestamp
    ticker: str
    company_name: str
    side: str  # "BUY" or "SELL"
    quantity: int
    price: float
    amount: float  # montant brut (quantité x prix), hors frais
    fees: float
    net_cost: float  # amount + fees (for buy) or amount - fees (for sell)
    recommendation: str
    confidence: float
    entry_confidence: Optional[float] = None

@dataclass
class Position:
    """Une position ouverte."""
    ticker: str
    company_name: str
    buy_date: pd.Timestamp
    buy_price: float
    buy_fees: float
    quantity: int
    current_price: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    entry_confidence: Optional[float] = None

@dataclass
class PortfolioSnapshot:
    """État du portefeuille à une date donnée."""
    date: pd.Timestamp
    cash: float
    positions: List[Position]
    gross_value: float = 0.0
    total_value: float = 0.0
    returns_pct: float = 0.0

class Backtester:
    """Simule les trades avec règles réalistes."""

    def __init__(self, initial_cash: Optional[float] = None, min_order_amount: Optional[float] = None):
        # Charger depuis la configuration si non fourni
        trading_params = config.get_section('trading')
        self.initial_cash = initial_cash or trading_params['initial_cash']
        self.min_order_amount = min_order_amount or trading_params['min_order_amount']

        # Les fondamentaux Yahoo sont ceux d'AUJOURD'HUI : les utiliser pour noter une date
        # passée est un biais d'anticipation. Désactivés par défaut (cf. DEC-09).
        self.use_fundamentals = bool(config.get('backtest.use_fundamentals'))

        self.cash = self.initial_cash
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.portfolio_history: List[PortfolioSnapshot] = []
        # Valeur du portefeuille à la clôture de CHAQUE séance (drawdown, volatilité)
        self.equity_curve: pd.Series = pd.Series(dtype=float)
        self.benchmark_ticker: str = config.get('backtest.benchmark')
        self.benchmark_data: Optional[pd.DataFrame] = None
        self.benchmark_curve: pd.Series = pd.Series(dtype=float)
        self.all_data: Dict[str, pd.DataFrame] = {}
        # Indicateurs calculés une fois par ticker sur tout l'historique : SMA/EMA/rolling
        # sont causaux, donc la ligne D ne dépend que des données <= D (cf. DEC-08).
        self.indicators: Dict[str, pd.DataFrame] = {}
        self.anomalies: Dict[str, pd.DatetimeIndex] = {}
        self._fundamentals_cache: Dict[str, Dict[str, Optional[float]]] = {}

    def load_data(self, tickers: List[str], period: Optional[str] = None):
        """Télécharge les données historiques journalières pour tous les tickers.

        Prix ajustés (auto_adjust=True) : dividendes et splits sont réintégrés dans la série,
        sinon un détachement de dividende ressemblerait à une chute de cours et le dividende
        ne serait jamais crédité au portefeuille.
        """
        period = period or config.get('backtest.data.period')
        print(f"📥 Téléchargement des données {period} pour {len(tickers)} actions...")
        for i, ticker in enumerate(tickers, 1):
            try:
                df = yf.download(
                    ticker,
                    period=period,
                    interval="1d",
                    auto_adjust=True,
                    progress=False
                )
                if df is not None and not df.empty:
                    self.add_price_data(ticker, df)
                    if i % 10 == 0:
                        print(f"  ✓ {i}/{len(tickers)} actions téléchargées")
            except Exception as e:
                print(f"  ✗ Erreur {ticker}: {e}")

        print(f"✓ {len(self.all_data)} actions chargées")

        try:
            bench = yf.download(self.benchmark_ticker, period=period, interval="1d",
                                auto_adjust=True, progress=False)
            if bench is not None and not bench.empty:
                self.benchmark_data = flatten_columns(bench)
                print(f"✓ Benchmark {self.benchmark_ticker} chargé")
        except Exception as e:
            print(f"  ✗ Benchmark {self.benchmark_ticker} indisponible: {e}")

    def add_price_data(self, ticker: str, df: pd.DataFrame):
        """Enregistre l'historique de prix d'un ticker et pré-calcule ses indicateurs."""
        df = flatten_columns(df)
        anomalies = split_anomalies(df, ticker)
        if not anomalies.empty:
            print(f"  ⚠ {ticker}: saut(s) de cours aberrant(s) le {', '.join(str(d.date()) for d in anomalies)}"
                  f" → indicateurs recalculés par segment (DEC-17)")
        self.all_data[ticker] = df
        self.anomalies[ticker] = anomalies
        indicators = prepare_indicators_by_segment(df, anomalies)
        if indicators is not None and not indicators.empty:
            self.indicators[ticker] = indicators

    def _fundamentals(self, ticker: str) -> Dict[str, Optional[float]]:
        """Fondamentaux Yahoo, récupérés une seule fois par ticker et par run."""
        if ticker not in self._fundamentals_cache:
            self._fundamentals_cache[ticker] = fetch_fundamentals_safe(ticker)
        return self._fundamentals_cache[ticker]

    def analyze_on_date(self, ticker: str, date: pd.Timestamp) -> Optional[Dict]:
        """Signal disponible à l'ouverture de `date`, exécutable au cours d'ouverture de `date`.

        Le signal n'utilise que les séances STRICTEMENT antérieures à `date` : on ne peut
        pas connaître la clôture du jour au moment de passer l'ordre (cf. DEC-09).
        Renvoie None si le titre ne cote pas ce jour-là.
        """
        df = self.indicators.get(ticker)
        prices = self.all_data.get(ticker)
        if df is None or prices is None or date not in prices.index:
            return None

        open_price = float(prices.loc[date, 'Open'])
        if not np.isfinite(open_price) or open_price <= 0:
            return None

        df_up_to_date = df[df.index < date]
        if df_up_to_date.empty:
            return None

        fundamentals = self._fundamentals(ticker) if self.use_fundamentals else {}
        snap = build_snapshot(df_up_to_date, fundamentals)

        # Vérifier que tous les indicateurs essentiels sont valides
        if snap.close is None or snap.sma200 is None:
            return None

        # Signal et exécution doivent être sur la même échelle de prix (cf. DEC-17)
        anomalies = self.anomalies.get(ticker, pd.DatetimeIndex([]))
        if ((anomalies > snap.date) & (anomalies <= date)).any():
            return None

        outcome = compute_score(snap)

        return {
            "ticker": ticker,
            "company_name": NOMS_ENTREPRISES.get(ticker, ticker),
            "date": date,
            "price": open_price,
            "signal_date": snap.date,
            "signal_close": snap.close,
            "recommendation": outcome["recommendation"],
            "confidence": outcome["confidence"],
            "score": outcome["score"],
            "technical_score": outcome["technical_score"],
            "snapshot": snap
        }

    def trading_calendar(self, start_date, end_date) -> pd.DatetimeIndex:
        """Séances cotées (au moins un titre de l'univers) entre deux dates incluses."""
        if not self.all_data:
            return pd.DatetimeIndex([])
        calendar = pd.DatetimeIndex(sorted(set().union(*(df.index for df in self.all_data.values()))))
        return calendar[(calendar >= pd.Timestamp(start_date)) & (calendar <= pd.Timestamp(end_date))]

    def rebalance_dates(self, start_date: str, end_date: str, frequency: str) -> List[pd.Timestamp]:
        """Premier jour de cotation de chaque période, d'après le calendrier réel des données.

        Les jours fériés (sans cotation) et les dates postérieures à la dernière cotation
        disponible sont ainsi exclus par construction (cf. DEC-09).
        """
        if frequency not in REBALANCE_FREQUENCIES:
            raise ValueError(f"trading.rebalance.frequency inconnue : {frequency!r} "
                             f"(attendu : {', '.join(REBALANCE_FREQUENCIES)})")
        calendar = self.trading_calendar(start_date, end_date)
        if calendar.empty:
            return []
        periods = calendar.to_period(REBALANCE_FREQUENCIES[frequency])
        return list(pd.Series(calendar, index=calendar).groupby(periods).first())

    def execute_rebalance(self, rebalance_date: pd.Timestamp,
                         tickers: List[str]):
        """Exécute une rebalance: évalue toutes les positions et agit."""
        print(f"\n{'='*60}")
        print(f"📅 REBALANCE du {rebalance_date.strftime('%Y-%m-%d')}")
        print(f"{'='*60}")
        print(f"💰 Cash disponible: {self.cash:.2f}€")
        print(f"📊 Positions ouvertes: {len(self.positions)}")

        # 1. Analyser TOUTES les actions
        analyses = {}
        scores_list = []
        for ticker in tickers:
            analysis = self.analyze_on_date(ticker, rebalance_date)
            if analysis:
                analyses[ticker] = analysis
                scores_list.append((analysis["company_name"], analysis["score"], analysis["recommendation"]))

        print(f"\n🔍 Analyses: {len(analyses)}/{len(tickers)} actions")

        # Afficher les top 5 scores (positifs et négatifs)
        if scores_list:
            scores_sorted = sorted(scores_list, key=lambda x: x[1], reverse=True)
            print(f"\n📊 Top 5 scores ACHAT:")
            for name, score, rec in scores_sorted[:5]:
                print(f"  {name:30s} | Score: {score:+6.2f} | {rec}")
            print(f"\n📊 Top 5 scores VENTE:")
            for name, score, rec in scores_sorted[-5:]:
                print(f"  {name:30s} | Score: {score:+6.2f} | {rec}")

        # 2. Évaluer les positions actuelles
        sells = []
        buys = []

        for ticker, position in list(self.positions.items()):
            if ticker in analyses:
                analysis = analyses[ticker]
                if analysis["recommendation"] == "VENTE":
                    sells.append((ticker, position, analysis, "VENTE"))
                elif self._stop_loss_hit(position, analysis["signal_close"]):
                    sells.append((ticker, position, analysis, "STOP-LOSS"))

        # 3. Chercher les bons achats
        for ticker, analysis in analyses.items():
            if ticker not in self.positions and analysis["recommendation"] == "ACHAT":
                buys.append((ticker, analysis))

        print(f"\n📉 VENTES proposées: {len(sells)}")
        for ticker, pos, analysis, reason in sells:
            print(f"  - {analysis['company_name']}: Prix={analysis['price']:.2f}€ | Motif: {reason} | Quantité={pos.quantity}")

        print(f"📈 ACHATS proposés: {len(buys)}")
        for ticker, analysis in buys:
            print(f"  + {analysis['company_name']}: Prix={analysis['price']:.2f}€ | Action suggérée: {analysis['recommendation']} | Confiance={analysis['confidence']:.2%}")

        # 4. Exécuter les ventes d'abord
        for ticker, position, analysis, reason in sells:
            self._execute_sell(position, analysis["price"], rebalance_date, reason)

        # 5. Exécuter les achats : meilleure probabilité d'abord, puis meilleur score technique
        #    (la table calibrée est par tranches, donc les ex-aequo sont fréquents)
        buys_sorted = sorted(buys, key=lambda x: (x[1]["confidence"], x[1]["technical_score"]), reverse=True)
        for ticker, analysis in buys_sorted:
            self._execute_buy(ticker, analysis, rebalance_date)

    def _stop_loss_hit(self, position: Position, last_close: float) -> bool:
        """Vrai si la dernière clôture connue est sous le prix d'achat de plus de stop_loss_pct.

        Contrôlé à chaque rebalance (pas en intrajournalier), sur la clôture de la veille,
        et exécuté à l'ouverture comme les autres ordres (cf. DEC-12).
        """
        stop_loss_pct = config.get('trading.exit_rules.stop_loss_pct')
        if stop_loss_pct is None:
            return False
        return last_close <= position.buy_price * (1 - stop_loss_pct / 100)

    def _execute_sell(self, position: Position, current_price: float,
                      date: pd.Timestamp, reason: str = "VENTE"):
        """Exécute une vente (motif : signal VENTE ou STOP-LOSS)."""
        amount = position.quantity * current_price
        fees = calculate_fees(amount)
        net_proceeds = amount - fees

        trade = Trade(
            date=date,
            ticker=position.ticker,
            company_name=position.company_name,
            side="SELL",
            quantity=position.quantity,
            price=current_price,
            amount=amount,
            fees=fees,
            net_cost=net_proceeds,
            recommendation=reason,
            confidence=0.0,
            entry_confidence=position.entry_confidence
        )

        self.trades.append(trade)
        self.cash += net_proceeds

        # Calculer PnL
        cost_basis = position.quantity * position.buy_price + position.buy_fees
        pnl = net_proceeds - cost_basis
        pnl_pct = (pnl / cost_basis * 100) if cost_basis > 0 else 0

        print(f"  ✓ {reason} {position.company_name}: {position.quantity} @ {current_price:.2f}€")
        print(f"    PnL: {pnl:.2f}€ ({pnl_pct:.2f}%) | Frais: {fees:.2f}€")

        del self.positions[position.ticker]

    def _execute_buy(self, ticker: str, analysis: Dict, date: pd.Timestamp):
        """Exécute un achat si possible."""
        margin_buffer = config.get('trading.margin_buffer')
        confidence = float(analysis['confidence'])
        min_order = float(self.min_order_amount)
        desired_amount = order_amount()

        # Respect available cash and safety buffer
        available_for_order = max(self.cash - margin_buffer, 0.0)
        budget = min(desired_amount, available_for_order)

        # If we can't reach the minimum order, skip the buy
        if budget < min_order:
            print(f"  ✗ ACHAT {analysis['company_name']}: Pas assez de cash ({self.cash:.2f}€ < {min_order:.2f}€)")
            return

        # Nombre ENTIER d'actions (pas de fractions chez Bourse Direct, cf. DEC-10) tel que
        # montant brut + frais <= budget. Les paliers de frais étant croissants,
        # frais(brut) <= frais(budget) garantit que le total tient dans le budget.
        price = analysis["price"]
        quantity = math.floor((budget - calculate_fees(budget)) / price)
        if quantity < 1:
            print(f"  ✗ ACHAT {analysis['company_name']}: 1 action ({price:.2f}€) dépasse le budget de {budget:.2f}€")
            return

        gross_amount = quantity * price
        fees = calculate_fees(gross_amount)
        total_cost = gross_amount + fees

        position = Position(
            ticker=ticker,
            company_name=analysis["company_name"],
            buy_date=date,
            buy_price=price,
            buy_fees=fees,
            quantity=quantity,
            entry_confidence=confidence
        )

        trade = Trade(
            date=date,
            ticker=ticker,
            company_name=analysis["company_name"],
            side="BUY",
            quantity=quantity,
            price=price,
            amount=gross_amount,
            fees=fees,
            net_cost=total_cost,
            recommendation="ACHAT",
            confidence=analysis["confidence"],
            entry_confidence=confidence
        )

        self.trades.append(trade)
        self.cash -= total_cost
        self.positions[ticker] = position

        print(f"  ✓ ACHAT {analysis['company_name']}: {quantity} @ {price:.2f}€ ({total_cost:.2f}€ frais inclus)")
        print(f"    Confiance: {analysis['confidence']:.2%} | Frais: {fees:.2f}€")

    def mark_to_market(self, date: pd.Timestamp):
        """Met à jour les prix des positions ouvertes."""
        for ticker, position in self.positions.items():
            if ticker in self.all_data:
                close = self.all_data[ticker]['Close'].asof(date)  # dernière clôture <= date
                if pd.notna(close):
                    position.current_price = float(close)
                    cost_basis = position.quantity * position.buy_price + position.buy_fees
                    position.pnl = (position.current_price * position.quantity) - cost_basis
                    position.pnl_pct = (position.pnl / cost_basis * 100) if cost_basis > 0 else 0

    def snapshot_portfolio(self, date: pd.Timestamp):
        """Crée une copie du portefeuille à une date."""
        self.mark_to_market(date)

        positions_copy = [
            Position(
                ticker=p.ticker,
                company_name=p.company_name,
                buy_date=p.buy_date,
                buy_price=p.buy_price,
                buy_fees=p.buy_fees,
                quantity=p.quantity,
                current_price=p.current_price,
                pnl=p.pnl,
                pnl_pct=p.pnl_pct
            )
            for p in self.positions.values()
        ]

        gross_value = self.portfolio_value()
        total_value = gross_value
        returns_pct = ((total_value - self.initial_cash) / self.initial_cash * 100)

        snapshot = PortfolioSnapshot(
            date=date,
            cash=self.cash,
            positions=positions_copy,
            gross_value=gross_value,
            total_value=total_value,
            returns_pct=returns_pct
        )

        self.portfolio_history.append(snapshot)

    def run_backtest(self, start_date: Optional[str] = None, end_date: Optional[str] = None):
        """Lance le backtest complet."""
        # Charger depuis la configuration si non fourni
        backtest_params = config.get_section('backtest')
        start_date = start_date or backtest_params['start_date']
        end_date = end_date or backtest_params['end_date']

        tickers = list(NOMS_ENTREPRISES.keys())

        print("\n" + "="*60)
        print("🚀 DÉMARRAGE DU BACKTEST")
        print("="*60)
        print(f"📈 Période: {start_date} à {end_date}")
        print(f"💰 Capital initial: {self.initial_cash}€")
        print(f"📊 Actions: {len(tickers)}")
        frequency = config.get('trading.rebalance.frequency')
        print(f"📌 Rebalance: {frequency} (1er jour de cotation, ordres au cours d'ouverture)")
        print(f"📌 Fondamentaux: {'activés (biais d anticipation !)' if self.use_fundamentals else 'désactivés'}")

        self.load_data(tickers)
        self.simulate(start_date, end_date, tickers, frequency)

    def simulate(self, start_date: str, end_date: str, tickers: List[str], frequency: str = "month"):
        """Rejoue la stratégie sur les données déjà chargées (sans accès réseau)."""
        rebalance_dates = self.rebalance_dates(start_date, end_date, frequency)
        if not rebalance_dates:
            print("Aucune date de rebalance : pas de données sur la période demandée.")
            return
        print(f"\n📅 {len(rebalance_dates)} rebalances, du {rebalance_dates[0].date()} au {rebalance_dates[-1].date()}")

        # Boucle journalière : ordres les jours de rebalance, valorisation chaque soir
        rebalance_set = set(rebalance_dates)
        sessions = self.trading_calendar(rebalance_dates[0], end_date)
        equity = {}
        for session in sessions:
            self._exit_on_price_anomaly(session)
            if session in rebalance_set:
                i = rebalance_dates.index(session) + 1
                print(f"\n[{i:2d}/{len(rebalance_dates)}] {session.strftime('%Y-%m-%d')}", end=" → ")
                self.execute_rebalance(session, tickers)
                self.snapshot_portfolio(session)
            else:
                self.mark_to_market(session)
            equity[session] = self.portfolio_value()

        # Photo finale à la dernière séance (et non à la dernière rebalance)
        if sessions[-1] not in rebalance_set:
            self.snapshot_portfolio(sessions[-1])

        # Point de départ : capital initial la veille de la première séance
        start = pd.Series({sessions[0] - pd.Timedelta(days=1): float(self.initial_cash)})
        self.equity_curve = pd.concat([start, pd.Series(equity)])
        self.benchmark_curve = self._benchmark_curve(sessions)

    def _exit_on_price_anomaly(self, session: pd.Timestamp):
        """Solde au dernier cours valide une position dont le cours saute de façon aberrante.

        Le cours publié après le saut n'est pas sur la même échelle (opération sur titre mal
        ajustée) : le valoriser créerait un gain ou une perte fictifs. On sort donc la ligne
        à la clôture de la veille, qui est le dernier prix comparable (cf. DEC-17).
        """
        for ticker, position in list(self.positions.items()):
            if session in self.anomalies.get(ticker, ()):
                closes = self.all_data[ticker]['Close']
                last_valid = float(closes[closes.index < session].iloc[-1])
                self._execute_sell(position, last_valid, session, "OST")

    def portfolio_value(self) -> float:
        """Cash + positions valorisées au dernier prix connu (après mark_to_market)."""
        return self.cash + sum(p.current_price * p.quantity for p in self.positions.values())

    def _benchmark_curve(self, sessions: pd.DatetimeIndex) -> pd.Series:
        """Achat-conservation du benchmark : tout le capital investi à l'ouverture de la
        première séance, en parts entières et frais inclus, comme la stratégie."""
        if self.benchmark_data is None or sessions.empty:
            return pd.Series(dtype=float)
        bench = self.benchmark_data
        first = sessions[0]
        if first not in bench.index:
            return pd.Series(dtype=float)
        open_price = float(bench.loc[first, 'Open'])
        units = math.floor((self.initial_cash - calculate_fees(self.initial_cash)) / open_price)
        leftover = self.initial_cash - units * open_price - calculate_fees(units * open_price)
        closes = bench['Close'].reindex(sessions, method='ffill')
        curve = leftover + units * closes
        start = pd.Series({first - pd.Timedelta(days=1): float(self.initial_cash)})
        return pd.concat([start, curve])

    def _confidence_bucket(self, confidence: Optional[float]) -> str:
        """Tranche de confiance d'achat = probabilité calibrée de la tranche de score (DEC-20)."""
        return "N/A" if confidence is None else f"{float(confidence):.3f}"

    def closed_trades(self) -> List[Dict]:
        """Allers-retours clôturés : chaque vente appariée au dernier achat du même titre.

        PnL NET = produit de vente après frais − coût d'achat frais inclus. C'est l'unique
        définition utilisée par le win rate et par le résumé par confiance (cf. DEC-11).
        """
        round_trips = []
        open_buys: Dict[str, Trade] = {}
        for trade in self.trades:
            if trade.side == "BUY":
                open_buys[trade.ticker] = trade
            elif trade.side == "SELL" and trade.ticker in open_buys:
                buy = open_buys.pop(trade.ticker)
                pnl = trade.net_cost - buy.net_cost
                round_trips.append({
                    "ticker": trade.ticker,
                    "buy_date": buy.date,
                    "sell_date": trade.date,
                    "exit_reason": trade.recommendation,
                    "entry_confidence": trade.entry_confidence,
                    "cost": buy.net_cost,
                    "proceeds": trade.net_cost,
                    "pnl": pnl,
                    "pnl_pct": pnl / buy.net_cost * 100 if buy.net_cost > 0 else 0.0,
                })
        return round_trips

    def get_confidence_pnl_summary(self) -> List[Dict]:
        """Retourne un résumé PnL par bucket de confiance d'achat."""
        buckets: Dict[str, List[Dict]] = {}
        for round_trip in self.closed_trades():
            buckets.setdefault(self._confidence_bucket(round_trip["entry_confidence"]), []).append(round_trip)

        summary = []
        for label in sorted(buckets, key=lambda b: (b == "N/A", b)):
            trips = buckets[label]
            wins = sum(1 for t in trips if t["pnl"] > 0)
            summary.append({
                "label": label,
                "trades": len(trips),
                "wins": wins,
                "losses": len(trips) - wins,
                "win_rate": wins / len(trips) * 100,
                "avg_pnl": sum(t["pnl"] for t in trips) / len(trips),
                "avg_pnl_pct": sum(t["pnl_pct"] for t in trips) / len(trips),
            })
        return summary

    def print_summary(self):
        """Affiche un résumé des performances."""
        if not self.portfolio_history:
            print("Aucun historique de portefeuille")
            return

        last = self.portfolio_history[-1]

        total_trades = len(self.trades)
        buy_trades = [t for t in self.trades if t.side == "BUY"]
        sell_trades = [t for t in self.trades if t.side == "SELL"]
        total_fees = sum(t.fees for t in self.trades)

        round_trips = self.closed_trades()
        wins = sum(1 for t in round_trips if t["pnl"] > 0)
        losses = len(round_trips) - wins

        win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0

        print("\n" + "="*60)
        print("📊 RÉSUMÉ DU BACKTEST")
        print("="*60)
        print(f"\n💰 RÉSULTATS FINANCIERS:")
        print(f"  Capital initial:     {self.initial_cash:>10.2f}€")
        print(f"  Valeur finale:       {last.total_value:>10.2f}€")
        print(f"  PnL absolu:          {last.total_value - self.initial_cash:>10.2f}€")
        print(f"  PnL %:               {last.returns_pct:>10.2f}%")

        if len(self.equity_curve) > 1:
            print(f"\n📉 PERFORMANCE & RISQUE (du {self.equity_curve.index[1].date()} au {self.equity_curve.index[-1].date()}):")
            columns = [("Stratégie", performance_metrics(self.equity_curve))]
            if len(self.benchmark_curve) > 1:
                columns.append((self.benchmark_ticker, performance_metrics(self.benchmark_curve)))
            print("  " + " " * 22 + "".join(f"{name:>14}" for name, _ in columns))
            for key, label in [("total_return_pct", "Rendement total %"), ("cagr_pct", "Rendement annualisé %"),
                               ("volatility_pct", "Volatilité annuelle %"), ("sharpe", "Sharpe (rf=0)"),
                               ("max_drawdown_pct", "Drawdown max %")]:
                print(f"  {label:<22}" + "".join(f"{metrics[key]:>14.2f}" for _, metrics in columns))

        print(f"\n📈 TRADES:")
        print(f"  Total trades:        {total_trades:>10}")
        print(f"  Achats:              {len(buy_trades):>10}")
        print(f"  Ventes:              {len(sell_trades):>10}")
        print(f"  Frais totaux:        {total_fees:>10.2f}€")

        if wins + losses > 0:
            stops = sum(1 for t in round_trips if t["exit_reason"] == "STOP-LOSS")
            print(f"\n✅ WIN RATE (allers-retours clôturés, nets de frais, dont {stops} stop-loss):")
            print(f"  Ventes gagnantes:    {wins:>10}")
            print(f"  Ventes perdantes:    {losses:>10}")
            print(f"  Win rate:            {win_rate:>10.2f}%")

        confidence_summary = self.get_confidence_pnl_summary()
        if confidence_summary:
            print(f"\n🎯 PnL PAR CONFIDENCE D'ACHAT:")
            for bucket in confidence_summary:
                print(
                    f"  {bucket['label']:<10} | trades={bucket['trades']:>3} | "
                    f"wins={bucket['wins']:>3} | losses={bucket['losses']:>3} | "
                    f"win_rate={bucket['win_rate']:>6.1f}% | avg_pnl={bucket['avg_pnl']:>8.2f}€"
                )

        print(f"\n📊 PORTEFEUILLE FINAL:")
        print(f"  Cash:                {last.cash:>10.2f}€")
        print(f"  Valeur positions:    {last.gross_value - last.cash:>10.2f}€")
        print(f"  Positions ouvertes:  {len(last.positions):>10}")

        if last.positions:
            print(f"\n📌 POSITIONS FINALES:")
            for pos in sorted(last.positions, key=lambda p: p.pnl, reverse=True):
                print(f"  {pos.company_name:20s}: {pos.quantity:>6d} @ {pos.current_price:>7.2f}€ | PnL: {pos.pnl:>8.2f}€ ({pos.pnl_pct:>6.2f}%)")

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

    # Charger depuis la configuration
    trading_params = config.get_section('trading')
    backtest_params = config.get_section('backtest')
    initial_cash = trading_params['initial_cash']
    min_order = trading_params['min_order_amount']
    start = backtest_params['start_date']
    end = backtest_params['end_date']

    backtester = Backtester(initial_cash=initial_cash, min_order_amount=min_order)
    backtester.run_backtest(start_date=start, end_date=end)
    backtester.print_summary()
