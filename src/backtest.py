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
    compute_score, fetch_fundamentals_safe, flatten_columns, order_amount_for_confidence,
    build_snapshot, prepare_indicators, NOMS_ENTREPRISES
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
        self.all_data: Dict[str, pd.DataFrame] = {}
        # Indicateurs calculés une fois par ticker sur tout l'historique : SMA/EMA/rolling
        # sont causaux, donc la ligne D ne dépend que des données <= D (cf. DEC-08).
        self.indicators: Dict[str, pd.DataFrame] = {}
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

    def add_price_data(self, ticker: str, df: pd.DataFrame):
        """Enregistre l'historique de prix d'un ticker et pré-calcule ses indicateurs."""
        df = flatten_columns(df)
        self.all_data[ticker] = df
        indicators = prepare_indicators(df)
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

        outcome = compute_score(snap)

        return {
            "ticker": ticker,
            "company_name": NOMS_ENTREPRISES.get(ticker, ticker),
            "date": date,
            "price": open_price,
            "signal_date": snap.date,
            "recommendation": outcome["recommendation"],
            "confidence": outcome["confidence"],
            "score": outcome["score"],
            "snapshot": snap
        }

    def rebalance_dates(self, start_date: str, end_date: str, frequency: str) -> List[pd.Timestamp]:
        """Premier jour de cotation de chaque période, d'après le calendrier réel des données.

        Les jours fériés (sans cotation) et les dates postérieures à la dernière cotation
        disponible sont ainsi exclus par construction (cf. DEC-09).
        """
        if frequency not in REBALANCE_FREQUENCIES:
            raise ValueError(f"trading.rebalance.frequency inconnue : {frequency!r} "
                             f"(attendu : {', '.join(REBALANCE_FREQUENCIES)})")
        if not self.all_data:
            return []

        calendar = pd.DatetimeIndex(sorted(set().union(*(df.index for df in self.all_data.values()))))
        calendar = calendar[(calendar >= pd.Timestamp(start_date)) & (calendar <= pd.Timestamp(end_date))]
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
                    sells.append((ticker, position, analysis))

        # 3. Chercher les bons achats
        for ticker, analysis in analyses.items():
            if ticker not in self.positions and analysis["recommendation"] == "ACHAT":
                buys.append((ticker, analysis))

        print(f"\n📉 VENTES proposées: {len(sells)}")
        for ticker, pos, analysis in sells:
            print(f"  - {analysis['company_name']}: Prix={analysis['price']:.2f}€ | Action suggérée: {analysis['recommendation']} | Quantité={pos.quantity}")

        print(f"📈 ACHATS proposés: {len(buys)}")
        for ticker, analysis in buys:
            print(f"  + {analysis['company_name']}: Prix={analysis['price']:.2f}€ | Action suggérée: {analysis['recommendation']} | Confiance={analysis['confidence']:.2%}")

        # 4. Exécuter les ventes d'abord
        for ticker, position, analysis in sells:
            self._execute_sell(position, analysis["price"], rebalance_date)

        # 5. Exécuter les achats (meilleure confiance en premier)
        buys_sorted = sorted(buys, key=lambda x: x[1]["confidence"], reverse=True)
        for ticker, analysis in buys_sorted:
            self._execute_buy(ticker, analysis, rebalance_date)

    def _execute_sell(self, position: Position, current_price: float,
                     date: pd.Timestamp):
        """Exécute une vente."""
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
            recommendation="VENTE",
            confidence=0.0,
            entry_confidence=position.entry_confidence
        )

        self.trades.append(trade)
        self.cash += net_proceeds

        # Calculer PnL
        cost_basis = position.quantity * position.buy_price + position.buy_fees
        pnl = net_proceeds - cost_basis
        pnl_pct = (pnl / cost_basis * 100) if cost_basis > 0 else 0

        print(f"  ✓ VENTE {position.company_name}: {position.quantity} @ {current_price:.2f}€")
        print(f"    PnL: {pnl:.2f}€ ({pnl_pct:.2f}%) | Frais: {fees:.2f}€")

        del self.positions[position.ticker]

    def _execute_buy(self, ticker: str, analysis: Dict, date: pd.Timestamp):
        """Exécute un achat si possible."""
        margin_buffer = config.get('trading.order_sizing.margin_buffer')
        confidence = float(analysis['confidence'])
        min_order = float(self.min_order_amount)
        max_order = float(config.get('trading.max_order_amount'))
        desired_amount = order_amount_for_confidence(confidence, min_order=min_order)

        # Respect available cash and safety buffer
        available_for_order = max(self.cash - margin_buffer, 0.0)
        order_amount = min(desired_amount, max_order, available_for_order)

        # If we can't reach the minimum order, skip the buy
        if order_amount < min_order:
            print(f"  ✗ ACHAT {analysis['company_name']}: Pas assez de cash ({self.cash:.2f}€ < {min_order:.2f}€)")
            return

        # Nombre ENTIER d'actions (pas de fractions chez Bourse Direct, cf. DEC-10) tel que
        # montant brut + frais <= budget. Les paliers de frais étant croissants,
        # frais(brut) <= frais(budget) garantit que le total tient dans le budget.
        price = analysis["price"]
        quantity = math.floor((order_amount - calculate_fees(order_amount)) / price)
        if quantity < 1:
            print(f"  ✗ ACHAT {analysis['company_name']}: 1 action ({price:.2f}€) dépasse le budget de {order_amount:.2f}€")
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
                df = self.all_data[ticker]
                df_up_to = df[df.index <= date]
                if not df_up_to.empty:
                    # use numpy value to avoid pandas single-element Series float deprecation
                    position.current_price = float(df_up_to['Close'].values[-1])
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

        gross_value = self.cash + sum(p.current_price * p.quantity for p in self.positions.values())
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

        # Obtenir les dates de rebalance
        rebalance_dates = self.rebalance_dates(start_date, end_date, frequency)
        if not rebalance_dates:
            print("Aucune date de rebalance : pas de données sur la période demandée.")
            return
        print(f"\n📅 {len(rebalance_dates)} rebalances, du {rebalance_dates[0].date()} au {rebalance_dates[-1].date()}")

        # Boucle principale
        for i, rebalance_date in enumerate(rebalance_dates, 1):
            pct = (i / len(rebalance_dates)) * 100
            print(f"\n[{i:2d}/{len(rebalance_dates)}] {pct:5.1f}% {rebalance_date.strftime('%Y-%m-%d')}", end=" → ")

            self.execute_rebalance(rebalance_date, tickers)
            self.snapshot_portfolio(rebalance_date)
            print(f"✓")

    def _confidence_bucket(self, confidence: Optional[float]) -> str:
        """Regroupe une confiance d'achat dans un bucket de 20% pour l'analyse."""
        if confidence is None:
            return "N/A"

        conf = float(confidence)
        if conf < 0.2:
            return "0.00-0.20"
        if conf < 0.4:
            return "0.20-0.40"
        if conf < 0.6:
            return "0.40-0.60"
        if conf < 0.8:
            return "0.60-0.80"
        return "0.80-1.00"

    def get_confidence_pnl_summary(self):
        """Retourne un résumé PnL par bucket de confiance d'achat."""
        sell_trades = [t for t in self.trades if t.side == "SELL" and t.entry_confidence is not None]
        buckets = {}
        last_buy_by_ticker = {}

        for trade in self.trades:
            if trade.side == "BUY":
                last_buy_by_ticker[trade.ticker] = trade
            elif trade.side == "SELL" and trade.ticker in last_buy_by_ticker:
                buy_trade = last_buy_by_ticker.get(trade.ticker)
                buy_value = buy_trade.net_cost
                sell_value = trade.net_cost
                pnl = sell_value - buy_value
                pnl_pct = (pnl / buy_value * 100) if buy_value > 0 else 0.0

                bucket = self._confidence_bucket(trade.entry_confidence)
                if bucket not in buckets:
                    buckets[bucket] = {
                        "label": bucket,
                        "trades": 0,
                        "wins": 0,
                        "losses": 0,
                        "win_rate": 0.0,
                        "avg_pnl": 0.0,
                        "avg_pnl_pct": 0.0,
                    }

                bucket_summary = buckets[bucket]
                bucket_summary["trades"] += 1
                bucket_summary["avg_pnl"] += pnl
                bucket_summary["avg_pnl_pct"] += pnl_pct
                if pnl > 0:
                    bucket_summary["wins"] += 1
                else:
                    bucket_summary["losses"] += 1

        summary = []
        for bucket_name in ["0.00-0.20", "0.20-0.40", "0.40-0.60", "0.60-0.80", "0.80-1.00"]:
            if bucket_name in buckets:
                bucket_summary = buckets[bucket_name]
                trades = bucket_summary["trades"]
                bucket_summary["win_rate"] = (bucket_summary["wins"] / trades * 100) if trades else 0.0
                bucket_summary["avg_pnl"] = (bucket_summary["avg_pnl"] / trades) if trades else 0.0
                bucket_summary["avg_pnl_pct"] = (bucket_summary["avg_pnl_pct"] / trades) if trades else 0.0
                summary.append(bucket_summary)

        return summary

    def print_summary(self):
        """Affiche un résumé des performances."""
        if not self.portfolio_history:
            print("Aucun historique de portefeuille")
            return

        first = self.portfolio_history[0]
        last = self.portfolio_history[-1]

        total_trades = len(self.trades)
        buy_trades = [t for t in self.trades if t.side == "BUY"]
        sell_trades = [t for t in self.trades if t.side == "SELL"]

        total_fees = sum(t.fees for t in self.trades)

        # Calculer win rate (ventes avec profit)
        wins = 0
        losses = 0
        for sell in sell_trades:
            # Trouver le buy correspondant
            buys_for_ticker = [t for t in buy_trades if t.ticker == sell.ticker and t.date < sell.date]
            if buys_for_ticker:
                last_buy = buys_for_ticker[-1]
                sell_value = sell.amount
                buy_value = last_buy.amount + last_buy.fees
                if sell_value > buy_value:
                    wins += 1
                else:
                    losses += 1

        win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0

        print("\n" + "="*60)
        print("📊 RÉSUMÉ DU BACKTEST")
        print("="*60)
        print(f"\n💰 RÉSULTATS FINANCIERS:")
        print(f"  Capital initial:     {self.initial_cash:>10.2f}€")
        print(f"  Valeur finale:       {last.total_value:>10.2f}€")
        print(f"  PnL absolu:          {last.total_value - self.initial_cash:>10.2f}€")
        print(f"  PnL %:               {last.returns_pct:>10.2f}%")

        print(f"\n📈 TRADES:")
        print(f"  Total trades:        {total_trades:>10}")
        print(f"  Achats:              {len(buy_trades):>10}")
        print(f"  Ventes:              {len(sell_trades):>10}")
        print(f"  Frais totaux:        {total_fees:>10.2f}€")

        if wins + losses > 0:
            print(f"\n✅ WIN RATE (Ventes):")
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
