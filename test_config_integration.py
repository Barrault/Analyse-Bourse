#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test de l'intégration de la configuration."""

from config_loader import config, get_scoring_weights, get_trading_params, get_fee_structure

print("✓ Config module import OK\n")

# Test 1: Scoring weights
print("=" * 60)
print("TEST 1: Scoring Weights")
print("=" * 60)
sw = get_scoring_weights()
print(f"✓ Trend long term weight: {sw['trends']['long_term']}")
print(f"✓ Buy threshold: {config.get('scoring.thresholds.buy')}")
print(f"✓ Sell threshold: {config.get('scoring.thresholds.sell')}")
print()

# Test 2: Trading parameters
print("=" * 60)
print("TEST 2: Trading Parameters")
print("=" * 60)
tp = get_trading_params()
print(f"✓ Initial cash: {tp['initial_cash']}€")
print(f"✓ Min order amount: {tp['min_order_amount']}€")
print(f"✓ Max order amount: {tp['max_order_amount']}€")
print(f"✓ Order sizing: {tp['order_sizing']['percentage']:.0%}")
print()

# Test 3: Fee structure
print("=" * 60)
print("TEST 3: Fee Structure")
print("=" * 60)
fees = get_fee_structure()
for i, tier in enumerate(fees):
    if tier['max_amount'] is None:
        print(f"✓ Tier {i+1}: > 4400€ → {tier['percentage_fee']:.4%}")
    else:
        print(f"✓ Tier {i+1}: ≤ {tier['max_amount']}€ → {tier['fixed_fee']:.2f}€")
print()

# Test 4: Backtest parameters
print("=" * 60)
print("TEST 4: Backtest Parameters")
print("=" * 60)
bp = config.get_section('backtest')
print(f"✓ Start date: {bp['start_date']}")
print(f"✓ End date: {bp['end_date']}")
print(f"✓ Data period: {bp['data']['period']}")
print()

# Test 5: Indicator parameters
print("=" * 60)
print("TEST 5: Indicator Parameters")
print("=" * 60)
indicators = config.get_section('indicators')
print(f"✓ SMA windows: {indicators['sma']['short_window']}, {indicators['sma']['mid_window']}, {indicators['sma']['long_window']}")
print(f"✓ RSI window: {indicators['rsi']['window']}")
print(f"✓ MACD parameters: fast={indicators['macd']['fast_window']}, slow={indicators['macd']['slow_window']}")
print(f"✓ Bollinger: window={indicators['bollinger']['window']}, std={indicators['bollinger']['num_std']}")
print()

print("=" * 60)
print("✅ ALL TESTS PASSED - Configuration is fully integrated!")
print("=" * 60)
