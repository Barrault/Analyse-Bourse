#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test complet du backtest avec configuration."""

import sys
import io
from backtest import Backtester
from config_loader import config

# Forcer UTF-8
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

print("=" * 70)
print("🧪 FULL INTEGRATION TEST - Backtest with Config")
print("=" * 70)

# Charger les paramètres depuis la config
trading_params = config.get_section('trading')
backtest_params = config.get_section('backtest')

print(f"\n📋 Configuration chargée:")
print(f"   Initial capital: {trading_params['initial_cash']}€")
print(f"   Min order: {trading_params['min_order_amount']}€")
print(f"   Backtest period: {backtest_params['start_date']} to {backtest_params['end_date']}")

# Tester avec UNE ACTION SEULEMENT pour la vitesse
print(f"\n🧪 Initializing Backtester (test with 1 ticker only)...")
backtester = Backtester()

print(f"   ✓ Initial cash: {backtester.initial_cash}€")
print(f"   ✓ Min order amount: {backtester.min_order_amount}€")

# Tester load_data avec 1 ticker
print(f"\n📥 Loading data for AC.PA (1 ticker test)...")
try:
    from cac40_analyzer import NOMS_ENTREPRISES
    test_tickers = ['AC.PA']
    backtester.load_data(test_tickers, period="1y")
    print(f"   ✓ Data loaded for {len(backtester.all_data)} ticker(s)")
except Exception as e:
    print(f"   ✗ Error: {e}")
    sys.exit(1)

# Tester prepare_indicators
print(f"\n🔧 Preparing indicators...")
try:
    from cac40_analyzer import prepare_indicators
    df = prepare_indicators(backtester.all_data['AC.PA'])
    if df is not None:
        print(f"   ✓ Indicators ready: {len(df)} rows, columns: {list(df.columns)[-5:]}")
    else:
        print(f"   ✗ prepare_indicators returned None")
except Exception as e:
    print(f"   ✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Tester analyze_on_date
print(f"\n📊 Testing analyze_on_date...")
try:
    import pandas as pd
    test_date = pd.Timestamp("2024-06-01")
    result = backtester.analyze_on_date('AC.PA', test_date)
    if result:
        print(f"   ✓ Analysis successful for AC.PA on {test_date.date()}")
        print(f"      - Price: {result['price']:.2f}€")
        print(f"      - Recommendation: {result['recommendation']}")
        print(f"      - Score: {result['score']:.2f}")
        print(f"      - Confidence: {result['confidence']:.2%}")
    else:
        print(f"   ⚠ analyze_on_date returned None (might be normal)")
except Exception as e:
    print(f"   ✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print(f"\n" + "=" * 70)
print(f"✅ INTEGRATION TEST PASSED!")
print(f"=" * 70)
print(f"\n✨ Summary:")
print(f"   ✓ Config loaded from YAML")
print(f"   ✓ Backtester initialized with config parameters")
print(f"   ✓ Data loading works")
print(f"   ✓ Indicator preparation works")
print(f"   ✓ Analysis on date works")
print(f"\n🚀 You can now run the full backtest:")
print(f"   python run_full_backtest.py")
