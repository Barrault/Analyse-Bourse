# Journal des décisions

Chaque entrée répond à un constat de [AUDIT.md](AUDIT.md) : **contexte → décision →
alternatives écartées → conséquences**. Les entrées sont ajoutées au fil des commits
de la branche `fix/audit-corrections`.

---

## DEC-00 — Organisation du travail git

- **Contexte** : ~30 constats touchant surtout 3 fichiers (`cac40_analyzer.py`, `backtest.py`, `config.yaml`).
- **Décision** : une seule branche `fix/audit-corrections` partant de `master`, un commit
  atomique par constat ou groupe de constats liés (format *Conventional Commits*,
  identifiant d'audit dans le message), puis une Pull Request vers `master`.
- **Écarté** : une branche par constat. Les corrections modifient les mêmes fonctions
  (`compute_score`, `execute_rebalance`) : des branches parallèles produiraient des
  conflits en chaîne sans bénéfice de revue, puisqu'un seul relecteur intervient.
- **Conséquences** : l'historique de la PR se lit commit par commit ; chaque commit laisse
  la suite de tests au vert (vérifié avant chaque commit).

---

## DEC-01 — Outillage : dépendances, pytest, layout (D2, D3, T1, T2, T3)

- **Contexte** : aucune liste de dépendances ; pytest absent ; tests mélangés au code dans
  `src/` ; deux « tests » sans assertion ; un test réseau qui appelle `sys.exit` à l'import ;
  un `src/__init__.py` qui laisse croire à un package alors que les modules s'importent à plat.
- **Décision** :
  - `requirements.txt` (exécution) et `requirements-dev.txt` (+ pytest), avec bornes
    `>=min,<majeure suivante` : on accepte les correctifs, pas les ruptures d'API.
    `yfinance>=0.2.54` est imposé car le format de `dividendYield` en dépend (DEC-02).
  - `pyproject.toml` minimal portant la config pytest : `pythonpath = ["src"]`, ce qui
    supprime les `sys.path.insert` dans les tests.
  - Tests déplacés dans `tests/`. Les scripts sans assertion sont remplacés par
    `tests/test_config.py`. Le test réseau devient un vrai test pytest marqué `network`,
    **exclu par défaut** (Yahoo est lent, limité en débit et non déterministe).
  - Suppression de `src/__init__.py`.
- **Écarté** : transformer `src/` en vrai package (`from src.config_loader import ...`).
  Cela casserait l'usage documenté `python src/cac40_analyzer.py` et imposerait
  `python -m`, pour un gain nul sur un projet personnel sans distribution.
- **Conséquences** : `pip install -r requirements-dev.txt && pytest` suffit depuis la racine.
