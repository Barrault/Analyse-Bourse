# Analyse boursière : actions françaises

Outil personnel d'aide à la décision pour un investissement mensuel sur actions
françaises. Il combine :

- **une analyse du jour** : score technique et fondamental, recommandation
  ACHAT / NEUTRE / VENTE, confiance et montant suggéré, avec les motifs en clair ;
- **un backtest** : rejoue la stratégie sur l'historique avec les frais Bourse Direct,
  des actions entières et un stop-loss, puis la compare à un ETF CAC 40.

> ⚠️ Outil personnel, pas un conseil en investissement. Voir les
> [limites du backtest](#limites-connues).

## Installation

Python 3.10 ou plus récent.

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (Linux/macOS : source .venv/bin/activate)
pip install -r requirements.txt   # ou requirements-dev.txt pour lancer les tests
```

## Utilisation

Les commandes se lancent depuis la racine du projet.

```bash
# Analyse du jour de tout l'univers (~96 valeurs)
python src/cac40_analyzer.py --period 5y

# Backtest complet (paramètres dans config/config.yaml)
python src/run_full_backtest.py
```

Le backtest écrit son journal dans `logs_results/backtest.log` et ses résultats (métriques
de la stratégie et du benchmark, PnL par tranche de confiance) dans
`results/backtest_results.json`. Ces deux dossiers sont ignorés par git.

## Fonctionnement

### Score

| Famille | Signaux (poids dans `scoring.*`) |
|---|---|
| Tendance | Cours > SMA200, SMA50 > SMA200, SMA20 > SMA50 |
| Momentum | MACD > 0, histogramme MACD > 0 |
| Oscillateurs | RSI (zone neutre, survente, surachat), bandes de Bollinger |
| Volume / volatilité | Volume > moyenne 20 j, ATR / cours sous un seuil |
| Fondamentaux | PE par tranches, P/B qualifié par le ROE implicite, croisement PE × P/B, dividende, pertes (BPA < 0) |

- Recommandation : `score ≥ thresholds.buy` → ACHAT, `score ≤ thresholds.sell` → VENTE,
  sinon NEUTRE.
- Confiance : 0,5 au seuil, puis 1,0 à `confidence_scale` points au-delà, avec des
  plafonds métier (fondamentaux faibles, titre déjà bradé, etc.).
- Montant suggéré (ACHAT seulement) : interpolation linéaire entre `min_order_amount` et
  `max_order_amount` selon la confiance. C'est la même règle que dans le backtest.

### Backtest

- Rebalance au **premier jour de cotation** de chaque période (`trading.rebalance.frequency`).
- Signal calculé sur les séances **antérieures**, ordres exécutés au **cours d'ouverture**.
- Ventes : signal VENTE ou **stop-loss** (clôture de la veille ≥ `stop_loss_pct` sous le
  prix d'achat).
- Achats : **actions entières**, frais Bourse Direct par paliers (`fees.structure`),
  réserve de trésorerie `margin_buffer`.
- Valorisation à chaque clôture. Rendement, volatilité, Sharpe (taux sans risque nul) et
  drawdown maximal, comparés à l'ETF **Amundi CAC 40 (`CAC.PA`)**, dividendes inclus.
- **Fondamentaux désactivés par défaut** (`backtest.use_fundamentals: false`) : Yahoo ne
  fournit que les valeurs actuelles, et s'en servir pour noter 2024 serait un biais
  d'anticipation.

### Limites connues

- **Biais du survivant** : l'univers correspond à la composition actuelle, et les
  sociétés disparues depuis 2024 manquent.
- **Fondamentaux non historiques** : le backtest par défaut évalue donc la partie technique
  de la stratégie seulement.
- Stop-loss vérifié une fois par période, pas en continu.
- Poids et seuils **non calibrés** : ce sont des choix d'expert, à ajuster en comparant
  au benchmark.

## Configuration

Tout se règle dans [config/config.yaml](config/config.yaml), sans toucher au code. Toutes
les clés sont obligatoires : une clé manquante ou mal orthographiée lève une erreur qui la
nomme. Des conseils de calibrage figurent en fin de fichier.

## Tests

```bash
pip install -r requirements-dev.txt
pytest              # tests hors réseau, lancés aussi par la CI GitHub Actions
pytest -m network   # test de bout en bout contre Yahoo Finance
```

## Structure

```
config/config.yaml        Paramètres (indicateurs, poids, trading, frais, backtest)
src/cac40_analyzer.py     Indicateurs, scoring, analyse du jour
src/backtest.py           Moteur de backtest, métriques, benchmark
src/run_full_backtest.py  Lancement du backtest avec journal et export JSON
src/config_loader.py      Lecture stricte de la configuration
tests/                    Suite pytest (données synthétiques, sans réseau)
docs/AUDIT.md             Audit du 2026-09-29 (constats identifiés A1…D4)
docs/DECISIONS.md         Journal des décisions : contexte, choix, alternatives
docs/ROADMAP.md           Pistes d'amélioration
CHANGELOG.md              Historique des versions
```
