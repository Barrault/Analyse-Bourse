# Development Roadmap & Git Branch Structure

## 📊 Project Phases

### ✅ Phase 0: Foundation (COMPLETED)
**Goal**: Build a working backtest engine
**Branch**: `feature/simple-backtest`

**Commits**:
```
ae2c17f - docs: Add comprehensive documentation
d79be93 - feature/simple-backtest: Add backtesting engine with fee simulation
```

**Status**: DONE ✅
- ✅ Backtester class with monthly rebalancing
- ✅ Bourse Direct fee calculation
- ✅ Trade & position tracking
- ✅ Quick test: **+7.1% on 3 months**
- ✅ Documentation complete

**Next**: Run full 2024-2026 backtest to get calibration data

---

## 🚀 Phase 1: Foundation & Data (Weeks 1-2)

### Branch: `feature/data-persistence`
**Goal**: Cache data to avoid re-downloading

```bash
git checkout -b feature/data-persistence
```

**Tasks**:
- [ ] Create `DataCache` class (CSV or SQLite)
- [ ] Save snapshots after each rebalance
- [ ] Load cached data if available
- [ ] Implement cache invalidation (1 week old?)

**Files to create**:
- `data_cache.py` - Cache management
- `cache/` - Directory for cached data

**Estimate**: 3-4 hours
**Testing**: Verify cache hit/miss

---

### Branch: `feature/config-yaml`
**Goal**: Externalize all parameters from code

```bash
git checkout -b feature/config-yaml
```

**Tasks**:
- [ ] Create `config.yaml` with all weights:
  ```yaml
  scoring:
    trends:
      long_term: 2.0
      mid_term: 1.2
      short_term: 1.0
    momentum:
      macd: 1.8
      histogram: 1.5
    rsi:
      normal: 0.5
      low: 1.0
      high: -1.5
    # ... etc

  thresholds:
    buy: 3
    sell: -3
    min_confidence: 0.0

  trading:
    min_order: 500
    max_order: 4400
  ```
- [ ] Load config in `cac40_analyzer.py`
- [ ] Make backtest parametric
- [ ] Add config validation

**Files to modify**:
- `cac40_analyzer.py` - Load from config
- `backtest.py` - Use config
- Create `config.yaml`

**Estimate**: 2-3 hours
**Testing**: Try 2-3 different configs, verify scores change

---

## 🔧 Phase 2: Optimization (Weeks 3-4)

### Branch: `feature/calibration`
**Goal**: Find optimal weights using backtest results

```bash
git checkout -b feature/calibration
```

**Prerequisites**: Full 2024-2026 backtest results

**Tasks**:
- [ ] Implement grid search:
  - Vary each weight ±20%
  - Run mini-backtests (sample month)
  - Track Sharpe ratio
- [ ] Identify best combination
- [ ] Document parameter sensitivity
- [ ] Create calibration report

**Files to create**:
- `calibration.py` - Grid search optimizer
- `calibration_results.json` - Results

**Estimate**: 6-8 hours
**Testing**: Compare optimized vs. original weights

---

### Branch: `feature/scoring-improvements`
**Goal**: Better fundamental analysis

```bash
git checkout -b feature/scoring-improvements
```

**Tasks**:
- [ ] **PE Analysis**:
  - Add PEG ratio (if growth available)
  - EV/EBITDA check
  - Detect value traps (high yield, declining earnings)

- [ ] **Dividend Safety**:
  - Payout ratio check
  - Dividend cut probability
  - Yield sustainability

- [ ] **Cross-signals**:
  - Require 2+ indicators for BUY
  - Avoid false signals
  - Confidence weighting

**Files to modify**:
- `cac40_analyzer.py` - New functions
- Add `fundamental_checks.py`

**Estimate**: 8-10 hours
**Testing**: Verify dividend traps detected

---

## 💼 Phase 3: Production Ready (Weeks 5-7)

### Branch: `feature/risk-management`
**Goal**: Proper position sizing and stops

```bash
git checkout -b feature/risk-management
```

**Tasks**:
- [ ] **Kelly Criterion**:
  - Estimate win rate from backtest
  - Calculate optimal bet size
  - Cap at 2% per position max

- [ ] **Stop-loss**:
  - Implement hard stops (e.g., -5%)
  - Trailing stops for winners
  - Exit on new VENTE signal

- [ ] **Correlation**:
  - Detect correlated positions
  - Limit sector exposure
  - Diversification rules

**Files to create**:
- `risk_management.py` - Sizing & stops
- Update `backtest.py` - Integrate stops

**Estimate**: 6-8 hours
**Testing**: Verify max drawdown reduced

---

### Branch: `feature/portfolio-tracking`
**Goal**: Real-time position monitoring

```bash
git checkout -b feature/portfolio-tracking
```

**Tasks**:
- [ ] Create `PortfolioManager` class:
  - Track actual positions vs. recommendations
  - Calculate unrealized PnL
  - Alert on major divergences

- [ ] Database schema:
  - Positions table
  - Transactions table
  - Daily snapshots

- [ ] Real-time updates:
  - Fetch current prices daily
  - Calculate metrics

**Files to create**:
- `portfolio_manager.py` - Live tracking
- `positions.db` - SQLite database

**Estimate**: 8-10 hours
**Testing**: Manual verification of calculations

---

### Branch: `feature/reporting`
**Goal**: Dashboard and analytics

```bash
git checkout -b feature/reporting
```

**Tasks**:
- [ ] **Performance Dashboard**:
  - Monthly PnL
  - Win rate
  - Sharpe ratio
  - Max drawdown

- [ ] **Trade Journal**:
  - All entry/exit prices
  - Reasons for trade
  - Performance per trade

- [ ] **HTML Report Generation**:
  - Automated monthly reports
  - Charts (matplotlib)
  - Email delivery option

**Files to create**:
- `reporting.py` - Report generation
- `templates/` - HTML templates
- `reports/` - Output directory

**Estimate**: 6-8 hours
**Testing**: Generate sample report manually

---

## 🏁 Phase 4: Polish & Production (Week 8)

### Branch: `feature/production`
**Goal**: Final integration and deployment prep

```bash
git checkout -b feature/production
```

**Tasks**:
- [ ] Integrate all features
- [ ] End-to-end testing
- [ ] Performance optimization
- [ ] Documentation updates
- [ ] CI/CD setup (if needed)

---

## 📊 Dependency Graph

```
Phase 0 (DONE)
    ├── feature/simple-backtest ✅
    │
Phase 1
    ├── feature/data-persistence
    ├── feature/config-yaml
    │
Phase 2
    ├── feature/calibration (requires Phase 1)
    ├── feature/scoring-improvements
    │
Phase 3
    ├── feature/risk-management
    ├── feature/portfolio-tracking (requires Phase 1)
    ├── feature/reporting
    │
Phase 4
    └── feature/production (requires all above)
```

---

## 🎯 Current Status

**Completed**: ✅ Backtesting engine with documentation
**In Progress**: ⏳ Full 2024-2026 backtest (30-45 min runtime)
**Next Steps**:
1. Get full backtest results
2. Decide: Optimize weights or move to Phase 1?
3. Create next feature branch

---

## 💡 Tips for Branch Management

### Starting a feature:
```bash
git checkout master
git pull origin master
git checkout -b feature/my-feature
# Make changes
git commit -m "feature: Description"
git push origin feature/my-feature
```

### Finishing a feature:
```bash
git checkout master
git pull origin master
git merge feature/my-feature
git push origin master
git branch -d feature/my-feature
```

### Testing before merge:
```bash
git checkout feature/my-feature
python quick_backtest.py  # Quick sanity check
```

---

## 📈 Success Metrics

By **end of Phase 3**, we should have:
- ✅ Optimized scoring weights
- ✅ Real-time position tracking
- ✅ Risk management (sizing & stops)
- ✅ Automated reporting
- ✅ Backtested performance: >5% annual return

By **end of Phase 4**:
- ✅ Production-ready system
- ✅ Automated monthly execution
- ✅ Full documentation
- ✅ Ready for real trading

---

*Estimated total development time: 8-10 weeks for full implementation*
*Current branch: `feature/simple-backtest`*
