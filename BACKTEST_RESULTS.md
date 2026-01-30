# CAC40 Stock Analyzer - Backtest Results & Development Plan

## 🎯 Project Vision
A strict stock analysis tool that recommends BUY/SELL signals for French CAC40+ stocks with:
- Technical indicators (SMA, EMA, RSI, MACD, Bollinger Bands, ATR)
- Fundamental analysis (PE, P/B, Dividend Yield)
- Real broker fees (Bourse Direct)
- Monthly rebalancing
- Portfolio simulation

## ✅ Completed: Feature 2 - Simple Backtest

### What works:
- ✅ Data download (5 years history)
- ✅ Monthly rebalancing
- ✅ Bourse Direct fee calculation
- ✅ Trade simulation
- ✅ Position tracking
- ✅ Performance reporting

### Quick Test Results (3 months: Jul-Sep 2024)
```
Capital initial:      5000.00€
Valeur finale:        5354.97€
PnL absolu:           +354.97€ (+7.10%)

Trades:
- Achats:  6 positions
- Ventes:  0 positions
- Frais:   10.58€ total

Final positions (all profitable except 1):
✅ Aramis Group:   +19.36%
✅ Sanofi:         +13.93%
✅ AXA:            +10.45%
✅ Euronext:        +7.49%
✅ Sodexo:          +0.44%
❌ TotalEnergies:   -1.97%
```

## 🚀 Next Steps - Development Roadmap

### Phase 1: Foundation (1-2 weeks)
- [ ] **Feature 1: Data Persistence**
  - Save/load snapshots to CSV or SQLite
  - Avoid re-downloading on every run
  - Branch: `feature/data-persistence`

- [ ] **Feature 3: Config Framework (YAML)**
  - Move hardcoded weights to config file
  - Enable easy parameter tuning
  - Branch: `feature/config-yaml`

### Phase 2: Optimization (2-3 weeks)
- [ ] **Feature 4: Calibration via Backtest**
  - Use backtest results to optimize weights
  - Grid search or Bayesian optimization
  - Find best threshold (+3 vs +5 for BUY?)
  - Branch: `feature/calibration`

- [ ] **Feature 5: Improved Scoring**
  - Better PE/PB analysis
  - Dividend safety checks
  - Cross-validation of signals
  - Branch: `feature/scoring-improvements`

### Phase 3: Production (2-3 weeks)
- [ ] **Feature 6: Risk Management**
  - Position sizing (Kelly criterion? Max 2% per position?)
  - Stop-loss automation
  - Correlation analysis
  - Branch: `feature/risk-management`

- [ ] **Feature 7: Portfolio Tracking**
  - Real-time position tracking
  - PnL monitoring
  - Alerts
  - Branch: `feature/portfolio-tracking`

- [ ] **Feature 8: Full Reporting**
  - Dashboard generation
  - Monthly performance reports
  - Trade journals
  - Branch: `feature/reporting`

## 📊 Current System Issues & Notes

### Strengths ✅
- Combines technical + fundamental analysis (rare)
- Strict thresholds prevent over-trading
- Real fee simulation
- Monthly rebalancing matches your trading style

### Known Issues ⚠️
- **Scoring weights are arbitrary** (no optimization yet)
- **No backtest validation** on historical data
- **No risk management** (no stop-loss, no sizing)
- **Dividend analysis weak** (doesn't detect traps)
- **Full 2024-2026 backtest needed** (not yet run)

### Technical Debt
- Long analysis time per rebalance (93 stocks × 30+ calculations each)
- Could optimize with caching or parallel processing
- Config is hardcoded in code

## 🔧 How to Run

### Quick test (3 months):
```bash
python quick_backtest.py
```

### Full backtest (2024-2026):
```bash
python backtest.py
```
*Warning: Takes 30-45 minutes for 93 stocks × 32 months*

### Test individual components:
```bash
python test_backtest.py
```

## 💰 Budget Context
- Initial capital: **5,000€**
- Trade frequency: **Monthly (1st trading day)**
- Order sizes: **500-1000€** (optimal fee range: 0.19%)
- Broker: **Bourse Direct** (see fee structure in backtest.py)

## 📝 Strategy Rules
1. **ACHAT**: Score >= +3 AND high confidence
2. **VENTE**: Score <= -3 AND open position
3. **NEUTRE**: Everything else (hold)
4. **Rebalance**: 1st trading day of each month
5. **Max positions**: Limited by capital (currently ~6)

## Next Immediate Action
Run full 2024-2026 backtest to get:
1. Expected annual return
2. Win rate on closed trades
3. Max drawdown
4. Sharpe ratio
Then use results to calibrate weights.

---
*Branch: feature/simple-backtest | Last update: 2026-01-30*
