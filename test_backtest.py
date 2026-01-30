"""
Version TEST du backtester - test rapide avec peu d'actions
"""
# -*- coding: utf-8 -*-
import sys
import io
from datetime import datetime
from backtest import Backtester, NOMS_ENTREPRISES

if __name__ == "__main__":
    # Forcer UTF-8
    if sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    # Tester avec juste 10 actions
    test_tickers = list(NOMS_ENTREPRISES.keys())[:10]
    print(f"🧪 TEST avec {len(test_tickers)} actions")
    print(f"Tickers: {test_tickers}")

    backtester = Backtester(initial_cash=5000, min_order_amount=500)

    # Charger les données
    backtester.load_data(test_tickers, period="5y")

    # Tester l'analyse pour un ticker
    from pandas import Timestamp
    test_date = Timestamp("2025-06-01")  # Après un an de données

    ticker = test_tickers[0]
    print(f"\n🧪 Test d'analyse pour {ticker} à {test_date}")

    # Test 1: Vérifier les données brutes
    if ticker in backtester.all_data:
        df = backtester.all_data[ticker]
        print(f"  - Données disponibles: {len(df)} jours")
        print(f"  - Dates: {df.index.min()} à {df.index.max()}")
        df_up_to = df[df.index <= test_date]
        print(f"  - Données jusqu'à {test_date}: {len(df_up_to)} jours")

    # Test 2: Préparer les indicateurs
    df_ind = backtester.prepare_indicators(ticker)
    if df_ind is not None:
        print(f"  - Indicateurs prêts: {len(df_ind)} jours")
        df_up_to_ind = df_ind[df_ind.index <= test_date]
        print(f"  - Indicateurs jusqu'à {test_date}: {len(df_up_to_ind)} jours")
        if not df_up_to_ind.empty:
            print(f"  - Dernière ligne:\n{df_up_to_ind.iloc[-1][['Close', 'SMA20', 'RSI14', 'MACD']].to_string()}")

    # Test 3: Analyser
    result = backtester.analyze_on_date(ticker, test_date)
    if result:
        print(f"  ✓ Analyse réussie: {result['recommendation']} (Conf: {result['confidence']:.2%})")
    else:
        print(f"  ✗ Analyse retourne None")

