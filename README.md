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

### Routine mensuelle (1er jour de bourse du mois, avant 9 h)

1. Exporter ses positions depuis Bourse Direct (fichier `…EUR-JJ_MM_AAAA HH_MM_SS.xlsx`
   dans Téléchargements).
2. Dans Claude Code : `/rebalance` (il demande les espèces disponibles de chaque compte),
   ou directement `python src/rebalance.py --list-exports` puis, pour chaque export retenu,
   `python src/rebalance.py --cash 1500 --export CHEMIN.xlsx`. Seuls les comptes exportés à
   la date la plus récente sont traités.
3. Le plan liste les ventes (signal VENTE ou stop-loss), puis les achats par priorité, avec
   quantités et montants frais inclus. Il est enregistré dans `journal/`, un fichier par compte (local, non
   versionné) pour suivre la performance réelle face à l'ETF.

Le backtest écrit son journal dans `logs_results/backtest.log` et ses résultats (métriques
de la stratégie et du benchmark, PnL par tranche de confiance) dans
`results/backtest_results.json`. Ces deux dossiers sont ignorés par git.

## Fonctionnement

### Score

| Famille | Signaux | Poids |
|---|---|---|
| Tendance | Cours > SMA200, SMA50 > SMA200, SMA20 > SMA50 | ±2,0 / ±1,2 / ±1,0 |
| Momentum | MACD > 0 | ±1,8 |
| Volume | Volume > moyenne sur 20 jours | ±0,5 |

Les autres règles techniques (histogramme MACD, RSI, Bollinger, volatilité) ont un
poids nul : elles n'ont montré aucun effet mesurable sur 2017-2021 (DEC-19).

- Recommandation : `score technique ≥ thresholds.buy` → ACHAT, `≤ thresholds.sell` →
  VENTE, sinon NEUTRE. L'analyse du jour applique donc exactement la stratégie testée.
- **Fondamentaux** (PE, P/B, dividende) : affichés pour information, sans effet sur la
  décision, faute d'historique pour les tester (DEC-24). Le dividende, seul testable, a
  changé d'effet selon les périodes (DEC-23). **Une seule exception** : pas d'ACHAT sur
  une entreprise en perte (`fundamentals.exclude_loss_making`).
- **Confiance = probabilité historique de battre le CAC 40 à 3 mois** pour ce niveau de
  score technique : p pour un ACHAT, 1 − p pour une VENTE. Elle est calibrée sur
  2017-2021 et vérifiée sur 2022-2026. Elle va de 44 % à 49 %, pour une moyenne de 47 % :
  l'avantage du score est réel mais modeste. Les ACHAT de même confiance sont départagés
  par le score technique, affiché sur chaque ligne.
- Montant suggéré (ACHAT seulement) : `trading.order_amount`, identique pour tous.

### Backtest

- Rebalance au **premier jour de cotation** de chaque période (`trading.rebalance.frequency`).
- Signal calculé sur les séances **antérieures**, ordres exécutés au **cours d'ouverture**.
- Ventes : signal VENTE ou **stop-loss** (clôture de la veille ≥ `stop_loss_pct` sous le
  prix d'achat).
- Achats : **actions entières**, montant identique, frais Bourse Direct par paliers
  (`fees.structure`), réserve de trésorerie `margin_buffer`. Quand le cash manque, les
  achats sont servis par probabilité, puis par score technique.
- **Contrôle des données** : un cours multiplié ou divisé par 2 en une séance (opération
  sur titre mal ajustée par Yahoo) découpe la série en segments, et une ligne détenue à ce
  moment est soldée au dernier cours valide (DEC-17).
- Valorisation à chaque clôture. Rendement, volatilité, Sharpe (taux sans risque nul) et
  drawdown maximal, comparés à l'ETF **Amundi CAC 40 (`CAC.PA`)**, dividendes inclus.
- **Fondamentaux désactivés par défaut** (`backtest.use_fundamentals: false`) : Yahoo ne
  fournit que les valeurs actuelles, et s'en servir pour noter le passé serait un biais
  d'anticipation.
- Période par défaut : 2022 → aujourd'hui, c'est-à-dire la **période de test**, sur
  laquelle aucun réglage n'a été choisi.

### Calibrage

Les réglages sont choisis sur la période d'**apprentissage** (`calibration.*`, 2017-2021)
et vérifiés sur la période de **test** (2022 → aujourd'hui) :

```bash
python src/calibrate.py features    # effet de chaque composante (apprentissage)
python src/calibrate.py calibrate   # table score -> probabilité à reporter dans la config
python src/calibrate.py evaluate    # fiabilité de cette table sur la période de test
python src/calibrate.py dividend    # le rendement du dividende prédit-il la performance ?
```

Ne jamais régler un paramètre en regardant la période de test : le résultat du backtest
perdrait toute valeur.

### Limites connues

- **Biais du survivant** : l'univers correspond à la composition actuelle, et les
  sociétés disparues depuis 2024 manquent.
- **Fondamentaux non historiques** : non testés, ils n'entrent pas dans la décision. Le
  filtre « entreprise en perte » est le seul élément de la stratégie non vérifié par les
  données.
- **Un seul chemin historique** : l'avance sur l'ETF en test (+2,7 points par an) est
  encourageante, mais reste compatible avec de la chance (DEC-22).
- Stop-loss vérifié une fois par période, pas en continu.
- Les **valeurs** des poids restent des choix d'expert. Seule leur sélection (poids
  nul ou non) est mesurée.

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
src/rebalance.py          Plan d'ordres mensuel depuis l'export de positions
.claude/                  Skill /rebalance et hooks Claude Code (tests avant commit)
src/calibrate.py          Calibrage (apprentissage) et évaluation (test)
tests/                    Suite pytest (données synthétiques, sans réseau)
docs/AUDIT.md             Audit du 2026-09-29 (constats identifiés A1…D4)
docs/DECISIONS.md         Journal des décisions : contexte, choix, alternatives
docs/ROADMAP.md           Pistes d'amélioration
CHANGELOG.md              Historique des versions
```
