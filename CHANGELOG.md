# Changelog

Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/). Les
identifiants (A1, S2…) renvoient à [docs/AUDIT.md](docs/AUDIT.md) et les choix sont
justifiés dans [docs/DECISIONS.md](docs/DECISIONS.md).

## [1.10.0] — 2026-10-28 — Nouveau style de l'extension

### Modifié
- Fenêtre de l'extension restylée dans l'esprit de Bourse Direct (bandeau bleu marine,
  sections en cartes, variations colorées, signaux en pastilles, thème sombre).

### Supprimé
- Bouton « Analyser cette page » : l'analyse automatique (DEC-30) suffit ; recharger la
  page après un échec (DEC-33).

## [1.9.0] — 2026-10-27 — Signaux ACHAT sans montant dans l'extension

### Modifié
- L'extension liste tous les signaux ACHAT par priorité (cours, score technique), sans
  quantité ni montant suggéré ; la confiance, identique pour tous les ACHAT, est donnée une
  fois ; la trésorerie s'arrête au solde après ventes. Le plan chiffré reste dans
  `rebalance.py` et le journal (DEC-32).

## [1.8.0] — 2026-10-27 — Analyse automatique dans l'extension

### Ajouté
- Sur « Mes portefeuilles », l'analyse du compte affiché se lance seule, sans clic, une fois
  par compte et par période de marché (avant 9 h, séance, après la clôture). Changer de
  compte sur le site lance l'analyse de l'autre compte (DEC-30).
- En séance, signaux réutilisés 15 min (`trading.rebalance.session_cache_minutes`) : le
  second compte est calculé en quelques secondes (DEC-31).

### Corrigé
- Un compte affiché pendant l'analyse d'un autre est copié aussitôt : revenir au premier
  compte avant la fin ne fait plus perdre le plan du second (DEC-31).

## [1.7.0] — 2026-10-27 — Un plan par compte dans l'extension

### Ajouté
- L'extension garde le dernier plan de chaque compte pendant la session du navigateur, et
  montre celui du compte affiché sur la page. Des onglets PEA / CTO donnent accès aux autres
  plans, sans relancer l'analyse (DEC-29).

## [1.6.0] — 2026-10-27 — Extension Opera

### Ajouté
- Extension Opera (`extension/`) : sur Bourse Direct, lit la page des positions et affiche
  le plan d'ordres. Lecture seule, aucun ordre passé (DEC-28).
- Hôte Native Messaging `src/native_host.py`, lancé par le navigateur : même chaîne que
  `rebalance.py`, journal par compte. Installation : `src/install_native_host.py`.

- Test de bout en bout de l'extension dans Chromium (`pytest -m browser`, Playwright) :
  copie anonymisée de la page, vrai hôte natif, affichage du plan.

### Modifié
- Signaux du jour mis en cache dans `results/` (hors séance) : le plan d'un deuxième compte
  est immédiat, en ligne de commande comme depuis l'extension.

## [1.5.0] — 2026-09-30 — Plusieurs comptes

### Modifié
- `/rebalance` traite chaque compte séparément (PEA, compte-titres). Exports retenus : la
  date la plus récente, puis l'export le plus récent de chaque compte à cette date ; un
  compte sans export ce jour-là est ignoré (`--list-exports`, DEC-26).
- Journal nommé par compte (`journal/AAAA-MM-JJ_<compte>.md`) : deux plans le même jour
  ne s'écrasent plus.
- Sans `--export`, le script refuse de choisir si plusieurs comptes ont un export à la
  même date.

## [1.4.0] — 2026-09-29 — Routine mensuelle outillée

### Ajouté
- `src/rebalance.py` et skill Claude Code `/rebalance` : depuis l'export de positions
  Bourse Direct, plan d'ordres conforme à la stratégie testée (ventes sur signal ou
  stop-loss, achats par priorité, actions entières, frais, réserve), écrit dans `journal/`.
- Hooks Claude Code : tests lancés avant chaque commit (blocage en cas d'échec), `git add`
  global bloqué.

### Modifié
- `analyze_ticker()` extrait de l'analyse du jour, partagé avec le plan de rebalance.

## [1.3.0] — 2026-09-29 — Décision sur ce qui est mesuré

### Modifié
- **La recommandation ne dépend plus que du score technique**, le seul mesuré. L'analyse
  du jour applique désormais exactement la stratégie évaluée par le backtest (DEC-24).
- Fondamentaux (PE, P/B, dividende) affichés pour information ; seul le filtre
  « pas d'ACHAT sur une entreprise en perte » agit (`fundamentals.exclude_loss_making`).
- Chaque ligne affiche le score technique, qui départage les ACHAT de même confiance.

### Ajouté
- `python src/calibrate.py dividend` : test du rendement du dividende reconstitué depuis
  l'historique Yahoo. Écarté, car son effet s'inverse entre 2017-2021 et 2022-2026 (DEC-23).

### Supprimé
- `scoring.fundamentals` (poids, tranches et seuils fixés à la main) et les alertes
  Value Support / Panic Sell.

## [1.2.0] — 2026-09-29 — Confiance calibrée

### Résultat hors échantillon (2022-01 → 2026-09, aucun réglage choisi sur cette période)

|                     | 1.1.0   | **1.2.0** | ETF CAC 40 |
|---------------------|--------:|----------:|-----------:|
| Rendement annualisé |  3,7 %  |  **8,4 %** |      5,6 % |
| Sharpe (rf = 0)     |   0,33  |   **0,57** |       0,41 |
| Drawdown max        | −23,3 % |   −20,9 % |    −20,9 % |

La version 1.1.0 faisait **moins bien** que l'ETF sur cette période plus longue. Le gain
vient de la sélection des composantes (ablation, DEC-22). Un seul chemin historique :
à confirmer en conditions réelles.

### Ajouté
- Contrôle qualité des cours : les sauts aberrants (regroupements, scissions mal ajustés
  par Yahoo) découpent la série en segments, et une position détenue est soldée « OST » (DEC-17).
- Protocole apprentissage (2017-2021) / test (2022 → aujourd'hui), historique de 10 ans,
  outil `src/calibrate.py` (DEC-18).

### Modifié
- Score technique réduit aux composantes ayant un effet mesuré : tendances, MACD, volume.
  Histogramme MACD, RSI, Bollinger et volatilité passent à un poids nul (DEC-19).
- **Confiance = probabilité calibrée de battre le CAC 40 à 3 mois** (44 à 49 %, moyenne
  47 %) ; les plafonds fondamentaux deviennent des alertes (DEC-20).
- Montant identique pour chaque achat : `trading.order_amount` (DEC-21).
- Le backtest par défaut porte sur la période de test (depuis 2022).

### Supprimé
- `scoring.confidence_scale`, `trading.max_order_amount`, `trading.order_sizing.*`.

## [1.1.0] — 2026-09-29 — Corrections de l'audit

### Résultat de référence

Backtest 2024-01-02 → 2026-09-29, fondamentaux désactivés, capital de 20 000 € :

|                       | Stratégie | ETF CAC 40 (`CAC.PA`) |
|-----------------------|----------:|----------------------:|
| Rendement total       |  +37,2 %  |               +16,0 % |
| Rendement annualisé   |  +12,2 %  |                +5,6 % |
| Volatilité annuelle   |   13,4 %  |                14,5 % |
| Sharpe (rf = 0)       |    0,91   |                  0,44 |
| Drawdown maximal      |  −12,8 %  |               −16,0 % |

Ce chiffre **n'est pas comparable** au +22,7 % publié avant l'audit : période, règles
d'exécution et biais corrigés sont différents. Il reste flatté par le biais du survivant
(voir les limites dans le README).

### Corrigé
- Rendement du dividende multiplié par 100 sous 1 % (A1).
- Rebalances à des dates futures ; jours fériés traités comme ouvrés (A2, B2).
- Biais d'anticipation : fondamentaux actuels utilisés pour le passé, exécution à la
  clôture qui produit le signal (A3, B2).
- Actions fractionnaires (A4).
- Plantage en fin de run à l'écriture des résultats (A5).
- Win rate incohérent entre deux rapports (B5).
- Sociétés en perte jamais pénalisées ; P/B élevé classé « toxique » ; double comptage
  du PE et du P/B (S1-S3).
- Confiance saturée ; montant suggéré pour les NEUTRE et VENTE (S4, S5).
- Seuil de volatilité jamais lu depuis la config (chemin erroné).

### Ajouté
- Benchmark ETF CAC 40 dividendes inclus ; rendement annualisé, volatilité, Sharpe et
  drawdown sur une valorisation journalière (B3).
- Stop-loss configurable (B4).
- Fréquence de rebalance configurable (semaine, mois, trimestre).
- Suite pytest : 40 tests hors réseau + 1 test réseau et CI GitHub Actions.
- `requirements.txt`, `requirements-dev.txt`, `pyproject.toml`.
- Audit, journal des décisions, roadmap.

### Modifié
- Config stricte : une clé manquante lève une erreur. Tous les seuils sont configurables,
  les clés inertes ont été supprimées.
- Backtest environ 60× plus rapide (≈ 30 s au lieu de 30-45 min) : indicateurs calculés
  une fois, fondamentaux en cache.
- Univers : `ARRJ.F` → `MT.AS`, doublon `ELIS.PA` supprimé.

### Supprimé
- `DEVELOPMENT.md`, `FEATURE_CONFIG.md`, `INTEGRATION_COMPLETE.md`, `BACKTEST_RESULTS.md`
  (périmés, voir DEC-16) ; scripts de test sans assertion ; code de debug.
