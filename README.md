# 📈 CAC40 Analyzer - Stock Analysis & Backtesting System

A **strict** French stock analyzer combining technical and fundamental analysis to generate BUY/SELL/HOLD signals for monthly rebalancing trading.

## Quick Start

### 1. Install dependencies
```bash
pip install pandas yfinance numpy ta
```

### 2. Run analysis (current date)
```bash
python cac40_analyzer.py --period 5y
```

### 3. Run backtest (3 months - fast test)
```bash
python quick_backtest.py
```

### 4. Run full backtest (2 years - 30-45 min)
```bash
python run_full_backtest.py > backtest_log.txt 2>&1 &
```

## 📊 System Overview

### Technical Indicators
- **Trends**: SMA20, SMA50, SMA200 (short/mid/long term)
- **Momentum**: MACD, MACD Histogram
- **Oscillators**: RSI14 (overbought/oversold)
- **Volatility**: Bollinger Bands, ATR14
- **Volume**: SMA20 of volume

### Fundamental Metrics
- **Valuation**: Trailing PE, Price-to-Book
- **Returns**: Implied ROE (approximation)
- **Income**: Dividend Yield

### Scoring & Recommendations
- **ACHAT (BUY)**: Score >= +3 (strict threshold)
- **VENTE (SELL)**: Score <= -3 (strict threshold)
- **NEUTRE (HOLD)**: Everything else
- Each signal includes confidence percentage

## 💰 Trading Parameters

| Parameter | Value |
|-----------|-------|
| Capital | 5,000€ |
| Rebalance Frequency | Monthly (1st trading day) |
| Min Order Size | 500€ (optimal fee: 0.19%) |
| Max Order Size | 1,000€ |
| Broker | Bourse Direct |
| Fee Structure | See `backtest.py` |

## 📁 File Structure

```
├── cac40_analyzer.py          # Main scoring engine
├── backtest.py                # Backtester class
├── quick_backtest.py          # 3-month test
├── run_full_backtest.py       # 2-year full test
├── test_backtest.py           # Component tests
├── BACKTEST_RESULTS.md        # Detailed results & roadmap
└── README.md                  # This file
```

## 🌳 Git Branches

### Completed ✅
- `feature/simple-backtest` - Backtesting with fee simulation

### In Progress 🔨
None yet - waiting for full backtest results

### Planned 📋
- `feature/data-persistence` - Cache downloaded data
- `feature/config-yaml` - Externalize parameters
- `feature/calibration` - Optimize scoring weights
- `feature/risk-management` - Position sizing, stops
- `feature/portfolio-tracking` - Real-time monitoring
- `feature/reporting` - Dashboard & analytics

## 🧪 Latest Test Results

**3-month backtest (Jul-Sep 2024):**
- PnL: **+354.97€ (+7.10%)**
- Trades: 6 buys, 0 sells
- Fees: 10.58€
- Avg position return: **+8.14%** (1 loser: -1.97%)

See [BACKTEST_RESULTS.md](BACKTEST_RESULTS.md) for full details.

## ⚠️ Known Limitations

1. **No optimization yet** - Scoring weights chosen arbitrarily
2. **Large datasets** - Backtesting 93 stocks takes time
3. **No caching** - Re-downloads data each run
4. **Basic fee modeling** - Assumes fixed execution price
5. **Dividend analysis weak** - Doesn't detect yield traps

## 🎯 Next Priorities

1. **✓ Build working backtest** (DONE)
2. **Run full 2024-2026 backtest** (IN PROGRESS)
3. **Optimize scoring weights** using backtest results
4. **Add risk management** (position sizing, stops)
5. **Cache data** for faster iterations

## 💡 Key Insights

### What's Working
- ✅ Combined technical + fundamental approach
- ✅ Strict thresholds reduce false signals
- ✅ Monthly rebalancing matches trader bandwidth
- ✅ Real fee simulation improves accuracy

### What Needs Work
- ❌ Scoring calibration (arbitrary weights)
- ❌ Dividend safety checks
- ❌ Risk management (no position sizing)
- ❌ Performance on full dataset unknown

## 🔗 References

### Scoring Logic
See `compute_score()` in `cac40_analyzer.py` for detailed weight allocation

### Fee Structure
Bourse Direct fees (compte-titres):
- ≤ 500€: 0.99€ fixed
- 500-1000€: 1.90€ fixed
- 1000-2000€: 2.90€ fixed
- 2000-4400€: 3.80€ fixed
- > 4400€: 0.09% of amount

## 📞 Support

For questions or improvements, check:
1. [BACKTEST_RESULTS.md](BACKTEST_RESULTS.md) - Detailed analysis
2. Commit messages - Development history
3. Branch PRs - Feature discussions

---

**Status**: Feature/simple-backtest complete. Awaiting full 2024-2026 results.
**Last Updated**: 2026-01-30
