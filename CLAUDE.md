# CLAUDE.md

Outil personnel d'analyse d'actions françaises (~96 valeurs type SBF 120) : score
technique → recommandation ACHAT / NEUTRE / VENTE mensuelle, plus un backtest réaliste
(frais Bourse Direct, actions entières, benchmark ETF CAC 40). Projet mené seul,
en français (code commenté, docs, échanges).

## Commandes (depuis la racine, venv `.venv`, Python 3.10)

```bash
pip install -r requirements-dev.txt
pytest                                   # tests hors réseau (~1 s), à lancer avant chaque commit
pytest -m network                        # test contre Yahoo, manuel
python src/cac40_analyzer.py --period 2y # analyse du jour
python src/run_full_backtest.py          # backtest ~30 s → logs_results/backtest.log, results/*.json
python src/calibrate.py {features|calibrate|evaluate|dividend}
```

Windows : préfixer par `PYTHONIOENCODING=utf-8` quand la sortie est redirigée (emojis).

## Architecture

- `src/cac40_analyzer.py` : indicateurs, contrôle qualité des cours, `compute_score`, analyse du jour
- `src/backtest.py` : `Backtester` (`add_price_data` → `simulate`), métriques, benchmark
- `src/calibrate.py` : sélection des composantes et table de confiance (apprentissage/test)
- `src/config_loader.py` : `config.get("a.b.c")`, **lève `KeyError`** si la clé manque
- `config/config.yaml` : tous les paramètres ; les poids sont annotés de leur effet mesuré
- `tests/conftest.py` : fixtures `snapshot`, `prices` (OHLCV synthétique), `no_fundamentals`

## Invariants à ne jamais casser

- **Pas d'anticipation** : signal calculé sur les séances **< J**, exécution à l'**ouverture
  de J**, valorisation à la clôture. Calendrier = jours réellement cotés. Tout nouveau calcul
  doit rester causal ; `test_signal_is_unchanged_when_same_day_and_future_data_change` le vérifie.
- **Apprentissage 2017-07 → 2021-09, test 2022 → aujourd'hui.** Aucun réglage choisi en
  regardant la période de test. Sélection d'une composante = règle fixée à l'avance (bon
  signe et t ≥ 1 sur l'apprentissage) ; on met à 0, on n'inverse ni n'optimise un poids.
- **La décision ne repose que sur le score technique.** Fondamentaux = information, plus
  un filtre (pas d'ACHAT si BPA < 0). L'analyse du jour doit rester identique à la stratégie
  backtestée.
- **Confiance = probabilité calibrée** de battre le CAC 40 à 3 mois (`scoring.confidence_calibration`).
  Après tout changement de poids : `calibrate`, puis `evaluate`, puis mise à jour de la table.
- **Toute clé de config est lue par le code** : pas de clé morte, pas de défaut codé en dur.

## Pièges Yahoo (yfinance)

- `dividendYield` est **déjà en %** ; `trailingPE` vaut `None` (pas négatif) en cas de perte,
  donc utiliser `trailingEps` ; un non-payeur a `dividendYield=None`, `trailingAnnualDividendRate=0`.
- Opérations sur titre mal ajustées (Atos, Vivendi) : sauts ×2 détectés, indicateurs calculés
  par segment. Vrais mouvements à mettre dans `data_quality.verified_real_moves`.
- En séance, Yahoo inclut la bougie du jour, incomplète : l'analyse se lance avant 9 h ou après la clôture.

## Workflow git

- Branche courte (`feat/…`, `fix/…`) puis **merge fast-forward dans `master`** et push ;
  **pas de Pull Request**. Supprimer la branche après fusion.
- Commits atomiques, *Conventional Commits* en anglais, chaque commit laisse `pytest` au vert.
- **Indexer les fichiers un par un**, jamais `git add -A` : l'utilisateur modifie parfois des
  fichiers en parallèle (ex. `.gitignore`).

## Documentation à tenir à jour (dans le même commit que le code)

- `docs/DECISIONS.md` : une entrée `DEC-xx` par choix non trivial (contexte → décision →
  alternatives écartées → conséquences). Dernière : DEC-24.
- `CHANGELOG.md` (version aussi dans `pyproject.toml`), `README.md` (état actuel seulement),
  `docs/ROADMAP.md` (pistes), `docs/AUDIT.md` (constats A1…D4, historique).
- Chiffres de performance : toujours avec la période et la comparaison à l'ETF, jamais seuls.
