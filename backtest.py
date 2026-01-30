"""
Backtester pour CAC40 Analyzer
Simule les trades réels avec frais Bourse Direct 2024-2026
"""
# -*- coding: utf-8 -*-
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np
import sys
import io
from cac40_analyzer import (
    sma, ema, rsi, macd, bollinger, atr, true_range,
    IndicatorSnapshot, compute_score, fetch_fundamentals_safe,
    build_snapshot, NOMS_ENTREPRISES
)

# ----------------------- Frais Bourse Direct ----------------------- #

def calculate_fees(amount: float) -> float:
    """Calcule les frais Bourse Direct pour un montant donné."""
    if amount <= 500:
        return 0.99
    elif amount <= 1000:
        return 1.90
    elif amount <= 2000:
        return 2.90
    elif amount <= 4400:
        return 3.80
    else:
        return amount * 0.0009

# ----------------------- Portfolio & Trade Tracking ----------------------- #

@dataclass
class Trade:
    """Enregistre un trade (achat ou vente)."""
    date: pd.Timestamp
    ticker: str
    company_name: str
    side: str  # "BUY" or "SELL"
    quantity: float
    price: float
    amount: float
    fees: float
    net_cost: float  # amount + fees (for buy) or amount - fees (for sell)
    recommendation: str
    confidence: float

@dataclass
class Position:
    """Une position ouverte."""
    ticker: str
    company_name: str
    buy_date: pd.Timestamp
    buy_price: float
    buy_fees: float
    quantity: float
    current_price: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0

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

    def __init__(self, initial_cash: float = 5000, min_order_amount: float = 500):
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.min_order_amount = min_order_amount
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.portfolio_history: List[PortfolioSnapshot] = []
        self.all_data: Dict[str, pd.DataFrame] = {}

    def load_data(self, tickers: List[str], period: str = "3y"):
        """Télécharge les données historiques pour tous les tickers."""
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
                    self.all_data[ticker] = df
                    if i % 10 == 0:
                        print(f"  ✓ {i}/{len(tickers)} actions téléchargées")
            except Exception as e:
                print(f"  ✗ Erreur {ticker}: {e}")

        print(f"✓ {len(self.all_data)} actions chargées")

    def prepare_indicators(self, ticker: str) -> Optional[pd.DataFrame]:
        """Prépare les indicateurs pour un ticker."""
        if ticker not in self.all_data:
            return None

        df = self.all_data[ticker].copy()

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

        return df.dropna()

    def analyze_on_date(self, ticker: str, date: pd.Timestamp) -> Optional[Dict]:
        """Analyse un ticker à une date spécifique."""
        df = self.prepare_indicators(ticker)
        if df is None or df.empty:
            return None

        # Trouver la dernière donnée avant ou à la date
        df_up_to_date = df[df.index <= date]
        if df_up_to_date.empty:
            return None

        fundamentals = fetch_fundamentals_safe(ticker)
        snap = build_snapshot(df_up_to_date, fundamentals)
        outcome = compute_score(snap)

        # Recalculer comme dans le code original
        total_score = outcome["score"]
        if total_score >= 3:
            outcome["recommendation"] = "ACHAT"
        elif total_score <= -3:
            outcome["recommendation"] = "VENTE"
        else:
            outcome["recommendation"] = "NEUTRE"
        outcome["confidence"] = min(max(abs(total_score) / 10, 0), 1.0)

        return {
            "ticker": ticker,
            "company_name": NOMS_ENTREPRISES.get(ticker, ticker),
            "date": date,
            "price": snap.close,
            "recommendation": outcome["recommendation"],
            "confidence": outcome["confidence"],
            "score": total_score,
            "snapshot": snap
        }

    def get_trading_days(self, start_date: str = "2024-01-01",
                        end_date: str = "2026-12-31",
                        frequency: str = "month") -> List[pd.Timestamp]:
        """Retourne les dates de rebalance (1er jour trading de chaque période)."""
        dates = pd.date_range(start=start_date, end=end_date, freq="MS")
        trading_dates = []

        for date in dates:
            # Trouver le premier jour de trading après cette date
            search_date = date
            for _ in range(7):  # Chercher dans les 7 prochains jours
                if search_date.weekday() < 5:  # 0-4 = lun-ven
                    trading_dates.append(search_date)
                    break
                search_date += timedelta(days=1)

        return trading_dates

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
        for ticker in tickers:
            analysis = self.analyze_on_date(ticker, rebalance_date)
            if analysis:
                analyses[ticker] = analysis

        print(f"\n🔍 Analyses: {len(analyses)}/{len(tickers)} actions")

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
            print(f"  - {analysis['company_name']}: {pos.quantity} @ {analysis['price']:.2f}€")

        print(f"📈 ACHATS proposés: {len(buys)}")
        for ticker, analysis in buys:
            print(f"  + {analysis['company_name']}: Conf={analysis['confidence']:.2%}")

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
            confidence=0.0  # TODO: get from analysis
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
        # Déterminer la taille de l'ordre
        # Stratégie: prendre 20-25% du cash disponible, min 500€, max le cash
        order_amount = min(
            max(self.cash * 0.25, self.min_order_amount),
            self.cash - 100  # Garder 100€ de marge
        )

        if order_amount < self.min_order_amount:
            print(f"  ✗ ACHAT {analysis['company_name']}: Pas assez de cash ({self.cash:.2f}€ < {self.min_order_amount}€)")
            return

        fees = calculate_fees(order_amount)
        actual_amount = order_amount - fees
        price = analysis["price"]
        quantity = actual_amount / price

        if self.cash < order_amount:
            print(f"  ✗ ACHAT {analysis['company_name']}: Cash insuffisant")
            return

        position = Position(
            ticker=ticker,
            company_name=analysis["company_name"],
            buy_date=date,
            buy_price=price,
            buy_fees=fees,
            quantity=quantity
        )

        trade = Trade(
            date=date,
            ticker=ticker,
            company_name=analysis["company_name"],
            side="BUY",
            quantity=quantity,
            price=price,
            amount=actual_amount,
            fees=fees,
            net_cost=order_amount,
            recommendation="ACHAT",
            confidence=analysis["confidence"]
        )

        self.trades.append(trade)
        self.cash -= order_amount
        self.positions[ticker] = position

        print(f"  ✓ ACHAT {analysis['company_name']}: {quantity:.2f} @ {price:.2f}€ ({order_amount:.2f}€)")
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

    def run_backtest(self, start_date: str = "2024-07-01",
                        end_date: str = "2026-12-31"):
        """Lance le backtest complet."""
        tickers = list(NOMS_ENTREPRISES.keys())

        print("\n" + "="*60)
        print("🚀 DÉMARRAGE DU BACKTEST")
        print("="*60)
        print(f"📈 Période: {start_date} à {end_date}")
        print(f"💰 Capital initial: {self.initial_cash}€")
        print(f"📊 Actions: {len(tickers)}")
        print(f"📌 Rebalance: Mensuelle (1er jour trading)")

        # Télécharger les données (charger 5 ans pour avoir assez d'historique)
        self.load_data(tickers, period="5y")

        # Obtenir les dates de rebalance
        rebalance_dates = self.get_trading_days(start_date, end_date, "month")
        print(f"\n📅 {len(rebalance_dates)} rebalances prévues")

        # Boucle principale
        for i, rebalance_date in enumerate(rebalance_dates, 1):
            pct = (i / len(rebalance_dates)) * 100
            print(f"\n[{i:2d}/{len(rebalance_dates)}] {pct:5.1f}% {rebalance_date.strftime('%Y-%m-%d')}", end=" → ")

            self.execute_rebalance(rebalance_date, tickers)
            self.snapshot_portfolio(rebalance_date)
            print(f"✓")

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

        print(f"\n📊 PORTEFEUILLE FINAL:")
        print(f"  Cash:                {last.cash:>10.2f}€")
        print(f"  Valeur positions:    {last.gross_value - last.cash:>10.2f}€")
        print(f"  Positions ouvertes:  {len(last.positions):>10}")

        if last.positions:
            print(f"\n📌 POSITIONS FINALES:")
            for pos in sorted(last.positions, key=lambda p: p.pnl, reverse=True):
                print(f"  {pos.company_name:20s}: {pos.quantity:>6.2f} @ {pos.current_price:>7.2f}€ | PnL: {pos.pnl:>8.2f}€ ({pos.pnl_pct:>6.2f}%)")

if __name__ == "__main__":
    # Forcer UTF-8
    if sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    backtester = Backtester(initial_cash=5000, min_order_amount=500)
    backtester.run_backtest(start_date="2024-01-01", end_date="2026-12-31")
    backtester.print_summary()
