# Changelog

Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/). Les
identifiants (A1, S2…) renvoient à [docs/AUDIT.md](docs/AUDIT.md) et les choix sont
justifiés dans [docs/DECISIONS.md](docs/DECISIONS.md).

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
