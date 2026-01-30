# Feature: Externalisation des Paramètres (config-yaml)

## ✅ Étape 1: Création de l'infrastructure (TERMINÉE)

### Fichiers créés:
- **`config.yaml`** : Fichier de configuration complète avec tous les paramètres
  - 40+ paramètres organisés par section
  - Commentaires détaillés pour la calibration

- **`config_loader.py`** : Module de gestion de la configuration
  - Pattern Singleton pour une seule instance
  - Méthodes pratiques pour accéder aux paramètres (par chemin, par section)
  - Validation basique
  - Fonctions de commodité pour les sections principales

### Sections de configuration:
1. **Indicateurs techniques** (windows, seuils RSI, paramètres MACD/Bollinger/ATR)
2. **Poids de scoring** (weights pour chaque indicateur + fondamentaux)
3. **Paramètres de trading** (cash initial, sizing, rebalancing)
4. **Structure tarifaire** (Bourse Direct)
5. **Paramètres de backtest** (dates, période de données)
6. **Output & Logging** (verbose, debug)

## 🚀 Étape 2: Intégration dans le code (À FAIRE)

### Pour `cac40_analyzer.py`:
1. Importer `config_loader`
2. Remplacer les valeurs hardcodées dans `compute_score()` par des appels à `config.get()`
3. Remplacer les paramètres des indicators dans `prepare_indicators()` (windows)
4. Exemple:
   ```python
   from config_loader import config

   # Au lieu de: if s.close > s.sma200:
   #             score += 2
   # Utiliser:   score += config.get('scoring.trends.long_term')
   ```

### Pour `backtest.py`:
1. Importer `config_loader`
2. Remplacer `calculate_fees()` par une fonction qui lit `fees.structure` depuis la config
3. Remplacer `initial_cash=5000, min_order_amount=500` par des valeurs de `trading`
4. Remplacer les paramètres de `prepare_indicators()` (windows SMA, RSI, etc)
5. Remplacer les dates de backtest dans `run_backtest()`
6. Utiliser la même logique de scoring que dans `cac40_analyzer`

### Pour `run_full_backtest.py`:
1. Charger les paramètres de backtest depuis la config
2. Utiliser `config.get('trading.initial_cash')` et `config.get('trading.min_order_amount')`
3. Utiliser `config.get('backtest.start_date')` et `config.get('backtest.end_date')`

## 📋 Checklist d'intégration:

- [ ] Modifier `prepare_indicators()` dans `cac40_analyzer.py`
- [ ] Modifier `compute_score()` dans `cac40_analyzer.py`
- [ ] Créer nouvelle `calculate_fees()` dans `backtest.py` (ou garder l'ancienne en fallback)
- [ ] Modifier `analyze_on_date()` dans `backtest.py`
- [ ] Modifier `__init__()` de `Backtester` pour charger depuis config
- [ ] Modifier `run_backtest()` pour utiliser les dates de config
- [ ] Modifier `run_full_backtest.py`
- [ ] Tester que tout fonctionne avec des paramètres par défaut
- [ ] Tester que modifier config.yaml change le comportement

## 🎯 Avantages finaux:
1. ✅ Modifier le comportement sans toucher au code
2. ✅ Facile à calibrer (changer scoring weights, thresholds, order sizing)
3. ✅ Facile à backtest avec différentes configurations
4. ✅ Une source unique de vérité pour les paramètres
5. ✅ Versionnage simple des configurations (git)

## 🔄 Flux de travail après intégration:
```bash
# Modifier les paramètres
vim config.yaml

# Relancer le backtest
python run_full_backtest.py

# Les changements sont appliqués automatiquement
```

---
**Statut**: Infrastructure terminée ✅
**Branche**: `feature/config-yaml`
**Prochaine étape**: Intégration dans le code
