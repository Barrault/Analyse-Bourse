# Audit du projet — 2026-09-29

Audit complet réalisé sur `master` @ `f86df24`. Chaque constat porte un identifiant
réutilisé dans les messages de commit et dans [DECISIONS.md](DECISIONS.md), où sont
justifiés les choix de correction.

Dernier backtest de référence (log du 2026-07-09) : **+22,73 %**, 362 trades,
win rate des ventes 31,9 %. Ce chiffre n'est pas fiable, pour les raisons ci-dessous.

## A — Bugs critiques (faussent les résultats)

| ID | Constat | Localisation (avant correction) | Preuve |
|----|---------|----------------------------------|--------|
| A1 | Rendement du dividende multiplié par 100 si < 1. yfinance le renvoie déjà en % | `cac40_analyzer.py:423` | `STMPA.PA` : 0,68 % affiché « 68.0 % », bonus « dividende élevé » (+1) |
| A2 | Rebalances à des dates futures : `end_date: 2026-12-31`, et la dernière cotation connue est réutilisée | `backtest.py:148`, `config.yaml:156` | Log du 2026-07-09 : rebalances 2026-09 → 2026-12 ; Safran/Bic/Interparfums à −0,99 € (frais seuls) |
| A3 | Biais d'anticipation : les fondamentaux **actuels** servent à noter les dates passées | `backtest.py:160` | Par construction |
| A4 | Actions fractionnaires (0,97 Safran), irréaliste chez Bourse Direct | `backtest.py:341` | Log : `Safran : 0.97 @ 335.10€` |
| A5 | `results/` relatif au répertoire courant et jamais créé → plantage en fin de run | `run_full_backtest.py:94` | Lecture du code |

## B — Biais méthodologiques du backtest

| ID | Constat |
|----|---------|
| B1 | Univers = liste actuelle (biais du survivant), ~97 titres type SBF120 et non CAC40 ; doublon `ELIS.PA` ; cotation Francfort `ARRJ.F` |
| B2 | Exécution au cours de clôture du jour du signal (look-ahead intra-journalier) ; jours fériés (1er janvier) traités comme ouvrés |
| B3 | Aucun benchmark (CAC40), ni drawdown, volatilité ou Sharpe |
| B4 | Aucune règle de sortie hors signal VENTE (pas de stop-loss) |
| B5 | Deux calculs de win rate incohérents (brut vs net) |

## S — Logique de scoring

| ID | Constat |
|----|---------|
| S1 | Sociétés en perte : yfinance renvoie `trailingPE=None` (pas négatif) → branche « PE négatif » jamais atteinte, aucune pénalité. Idem `dy == 0` jamais atteint (`None`) |
| S2 | P/B > 2,5 classé « toxique » → valeurs de qualité (LVMH, Hermès, Safran…) en vente à ≥ 0,90 de confiance |
| S3 | Double comptage : PE noté 3 fois (tranches, continu, ROE implicite), P/B 3 fois |
| S4 | Confiance saturée dès score = 6 |
| S5 | Montant suggéré affiché pour NEUTRE/VENTE ; tri final mélangeant les recommandations ; dimensionnement différent de celui du backtest |
| S6 | Code mort (`fund_score`) |

## C — Configuration et code

| ID | Constat |
|----|---------|
| C1 | Clés ignorées : `macd.*`, `cheap_with_growth`, `dividend.medium_yield`, `order_sizing.type/percentage`, `rebalance.*`, `backtest.data.*`, `output.*`, doublon `max_order_amount` |
| C2 | Seuils fondamentaux en dur (PE 8/14/22, P/B 1/2,5, ROE 10/12, dividende 2/5…) |
| C3 | `config.get()` renvoie `None` silencieusement sur une clé mal orthographiée |
| C4 | Code de debug en dur (`AC.PA`, 2024-07-01) |
| C5 | Duplication de l'aplatissement MultiIndex ; imports inutilisés |
| C6 | Commentaires de config faux ou obsolètes |

## P — Performance

| ID | Constat |
|----|---------|
| P1 | ~3 500 recalculs complets d'indicateurs et ~3 500 appels réseau `Ticker.info` par backtest (30-45 min) |

## T — Tests

| ID | Constat |
|----|---------|
| T1 | pytest absent de l'environnement |
| T2 | `test_config_integration` / `test_config_modification` : scripts sans assertion |
| T3 | `test_full_integration` : réseau + `sys.exit` à l'import (casse la collecte pytest) |
| T4 | Aucun test sur frais, sizing, non-anticipation |

## D — Documentation et packaging

| ID | Constat |
|----|---------|
| D1 | README obsolète (`quick_backtest.py` inexistant, `ta` inutile, seuils/capital faux, chemins faux) |
| D2 | Pas de `requirements.txt` ; PyYAML non documenté |
| D3 | Imports fonctionnels uniquement depuis `src/` malgré `src/__init__.py` |
| D4 | 4 fichiers `.md` redondants et périmés |
