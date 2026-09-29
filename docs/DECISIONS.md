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

---

## DEC-02 — Rendement du dividende (A1)

- **Contexte** : le code multipliait `dividendYield` par 100 s'il était < 1, héritage de
  l'ancien format yfinance (fraction). Depuis yfinance 0.2.54 la valeur est déjà en %.
  Tout titre versant moins de 1 % était donc crédité d'un rendement de 50 à 99 %.
- **Décision** : lire la valeur telle quelle et imposer `yfinance>=0.2.54` dans
  `requirements.txt`, ce qui garantit le format.
- **Écarté** : une heuristique qui devine le format selon l'ordre de grandeur. Elle
  est indécidable : 0,5 peut valoir 0,5 % (nouveau format) ou 50 % (ancien format).
  Fixer la version de la dépendance lève l'ambiguïté à la source.
- **Conséquences** : les valeurs à rendement < 1 % (STMicro, Dassault Systèmes…) ne
  touchent plus le bonus « dividende élevé ». Test : `tests/test_fundamentals.py`.

---

## DEC-03 — Configuration stricte (C3)

- **Contexte** : `config.get()` renvoyait `None` pour une clé absente. Une faute de frappe
  dans le YAML ne se voyait qu'au plantage d'une comparaison `None > float`, ou pire,
  était masquée par une valeur par défaut codée en dur. Cas réel trouvé :
  `compute_score` lisait `indicators.volatility.threshold` alors que la clé est
  `scoring.volatility.threshold`. La valeur du YAML n'a donc **jamais** été utilisée
  (le défaut 0.04 coïncidait par hasard).
- **Décision** : `get(path)` lève `KeyError` avec le chemin fautif si la clé manque. Un
  défaut n'est possible que s'il est passé **explicitement**. Suppression des défauts codés
  en dur (frais, sizing) : le YAML est l'unique source de vérité. Le singleton `__new__`
  et les fonctions de commodité inutilisées sont retirés : une instance au niveau du
  module est déjà un singleton en Python.
- **Écarté** : une validation par schéma (pydantic, jsonschema). C'est plus complet, mais
  cela ajoute une dépendance et un schéma à maintenir en double du YAML. L'échec au premier
  accès couvre le besoin réel, à savoir détecter une clé mal orthographiée.
- **Conséquences** : une config incomplète échoue tôt, avec un message qui nomme la clé.

---

## DEC-04 — Chemins de sortie du backtest complet (A5)

- **Contexte** : `results/` était résolu par rapport au répertoire courant et jamais créé.
  Le run plantait donc **à la fin**, après 30 à 45 minutes, sauf s'il était lancé depuis
  un dossier qui contenait déjà `results/`. De plus, `sys.stdout` n'était pas restauré
  après la fermeture du fichier de log.
- **Décision** : ancrer les chemins sur la racine du projet (`Path(__file__).parent.parent`),
  créer le dossier avant l'écriture (`mkdir(parents=True, exist_ok=True)`), restaurer
  stdout/stderr dans le `finally`. Nom de fichier générique (`backtest_results.json`,
  `backtest.log`) : les dates vivent dans la config, pas dans les noms de fichiers.
  `logs_results/` et `results/` sont ignorés par git.
- **Écarté** : remplacer `DualLogger` par le module `logging`. Ici la sortie console **est**
  le rapport destiné à l'utilisateur, pas un journal technique. `logging` ajouterait des
  préfixes et une configuration sans rien apporter.

---

## DEC-05 — Nettoyage : debug, duplication, encodage (C4, C5)

- **Décision** :
  - Suppression du code de debug codé en dur (`AC.PA`, 2024-07-01). Un diagnostic ciblé
    se fait au débogueur ou par un test, pas par un `print` conditionnel qui reste dans le code.
  - L'aplatissement du MultiIndex yfinance, présent en double, devient
    `flatten_columns()` dans `cac40_analyzer.py` et est testé.
  - Imports inutilisés retirés. `sys.stdout.reconfigure(encoding='utf-8')` remplace le
    ré-enveloppement `io.TextIOWrapper`. C'est l'API prévue pour cela depuis Python 3.7 :
    elle garde le même objet stream et n'en crée pas un second sur le même buffer.
