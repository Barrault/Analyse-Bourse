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

---

## DEC-06 — Scoring fondamental (S1, S2, S3, S6, C2)

- **Contexte** :
  - S1 : yfinance ne publie jamais de PE négatif (`trailingPE=None` en cas de perte) ni de
    rendement nul (`None` pour un non-payeur). Les branches « PE négatif » et « aucun
    dividende » étaient donc du code mort, et **une société en perte n'avait aucune
    pénalité**. Vérifié sur UBI, ATOS et STMPA le 2026-09-29.
  - S2 : P/B > 2,5 déclenchait le drapeau « toxique », qui force la confiance de vente à 0,90.
  - S3 : le PE était noté 3 fois (tranches, terme continu `pe_scale`, bonus ROE) et le P/B
    3 fois. Le poids réel des fondamentaux ne correspondait plus à celui lu dans le YAML.
  - C2 : 15 seuils codés en dur ; S6 : `tech_score` et `fund_score` calculés sans être utilisés.
- **Décision** :
  - Perte détectée par `trailingEps < 0` (nouveau champ récupéré) : pénalité
    `pe.negative = -2.0`, alignée sur `pe.high`, et drapeau toxique. Une entreprise en
    perte ne doit pas être mieux notée qu'une entreprise rentable mais chère.
  - Non-payeur détecté par `trailingAnnualDividendRate == 0` → `dy = 0`. Un `None`
    persistant reste « inconnu » et n'est pas pénalisé.
  - **Toxique = pertes uniquement.** Un P/B élevé reste une pénalité de score
    (`pb.high`) et un drapeau « faible », mais pas « toxique » : il est structurel pour
    les modèles à actifs légers (luxe, logiciel), où les fonds propres comptables
    sous-estiment la valeur.
  - **Une contribution par métrique.** Les tranches sont conservées ; le terme continu
    et le bonus ROE autonome sont supprimés. Le ROE implicite ne sert plus qu'à qualifier
    le P/B, ce qui était déjà son rôle dans les tranches.
  - Tous les seuils passent dans `scoring.fundamentals.limits`. Les clés mortes
    `value_confirmation` et `dividend.medium_yield` sont remplacées par la clé existante
    `cheap_with_growth` et par une tranche neutre documentée.
- **Écarté** : garder le terme continu et supprimer les tranches. Le terme continu est un
  bonus borné à 0 : il ne pénalise jamais un PE élevé et ne permet pas l'interaction avec
  la tendance (PE raisonnable *et* tendance haussière). Les tranches sont aussi celles
  qu'expliquent les motifs affichés à l'utilisateur.
- **Conséquences** : l'amplitude du score fondamental baisse d'environ 3 points pour les
  valeurs décotées. Le seuil d'achat (4) n'a pas été recalibré : cela relève d'une
  campagne de calibrage sur un backtest désormais honnête (DEC-09), pas d'un correctif.
  Chaque nouveau comportement a un test qui échoue sur l'ancien code.

---

## DEC-07 — Confiance et montant suggéré (S4, S5)

- **Contexte** : la confiance valait `(score − seuil)/|seuil| + 0,5` plafonnée à 1. Avec
  un seuil d'achat de 4, elle saturait dès un score de 6 et ne distinguait plus un bon
  signal d'un excellent. Le montant suggéré de l'analyse (`confiance × 1000`) différait
  du dimensionnement du backtest (min/max interpolé), était affiché pour les NEUTRE et
  les VENTE, et le tri final mélangeait les trois recommandations.
- **Décision** :
  - `signal_confidence(distance)` : 0,5 au seuil, linéaire jusqu'à 1,0 à
    `scoring.confidence_scale = 8` points au-delà. 8 correspond à l'écart entre le seuil
    d'achat (4) et un score quasi maximal (~12 ; le maximum théorique est ~14).
  - `order_amount_for_confidence()` : une seule règle de dimensionnement, utilisée par
    l'analyse et par le backtest. Le montant suggéré ne concerne que les ACHAT (0 sinon,
    et masqué à l'affichage).
  - Tri de la sortie : ACHAT, puis NEUTRE, puis VENTE, par confiance décroissante.
  - Config : suppression du doublon `order_sizing.max_order_amount` et des clés inertes
    `order_sizing.type` et `percentage`.
- **Écarté** : une confiance sigmoïde. Elle est plus « jolie », mais moins lisible et
  demande un paramètre de plus sans justification empirique à ce stade.
- **Conséquences** : pour un même score, la confiance est plus basse qu'avant, donc les
  ordres sont plus petits. Les plafonds métier (0,40 si fondamentaux faibles, 0,90
  plancher en cas de pertes, etc.) sont inchangés.

---

## DEC-08 — Performance du backtest (P1)

- **Contexte** : à chaque rebalance, et pour chaque ticker, `analyze_on_date` recalculait
  tous les indicateurs sur 5 ans et appelait `yf.Ticker(t).info` en réseau, soit environ
  3 500 recalculs complets et 3 500 requêtes HTTP par run (30-45 min, avec un risque de
  limitation de débit par Yahoo).
- **Décision** : indicateurs calculés **une fois** par ticker au chargement
  (`add_price_data`), puis tronqués à la date analysée ; fondamentaux mis en cache par
  ticker pour la durée du run.
- **Justification de l'équivalence** : SMA, EMA, RSI (EWM), Bollinger et ATR sont des
  calculs causaux, où la valeur en D ne dépend que des données ≤ D. Pré-calculer sur tout
  l'historique puis tronquer donne donc le même résultat que calculer sur l'historique
  tronqué. Le test `test_precomputed_indicators_match_a_computation_on_truncated_history`
  vérifie cette égalité.
- **Écarté** : un cache disque (CSV/SQLite, prévu dans l'ancienne roadmap). Il est utile
  entre deux runs, mais ajoute de l'invalidation à gérer. Le cache mémoire suffit à
  supprimer l'essentiel du coût.
- **Conséquences** : `add_price_data()` permet aussi d'injecter des données synthétiques,
  ce qui rend le moteur testable sans réseau (fixtures `prices` et `no_fundamentals`).

---

## DEC-09 — Suppression des biais d'anticipation (A2, A3, B2, C1 partiel)

- **Contexte** : trois fuites d'information du futur.
  1. A2 : les dates de rebalance étaient générées jusqu'au 31/12/2026, et la dernière
     cotation connue était réutilisée pour les dates futures. Le log du 2026-07-09 contient
     4 rebalances fictives (septembre à décembre 2026).
  2. B2 : le signal était calculé avec la clôture du jour J et exécuté… à cette même
     clôture. Or un ordre ne peut pas utiliser une information qui n'existe qu'à la fin de
     la séance où il est passé. Le 1er janvier (bourse fermée) était en outre traité comme
     un jour ouvré.
  3. A3 : les fondamentaux utilisés pour une date de 2024 étaient ceux publiés en 2026.
- **Décision** :
  1. Calendrier = **jours réellement cotés** dans les données (`rebalance_dates`) : les
     jours fériés et les dates futures sont exclus par construction. La fréquence
     `trading.rebalance.frequency` (week/month/quarter), jusque-là ignorée, est câblée.
  2. Signal calculé sur les séances **strictement antérieures** à J et exécuté au **cours
     d'ouverture de J**. Un titre qui ne cote pas en J n'est pas traité ce jour-là.
     La valorisation du portefeuille reste faite à la clôture de J.
  3. `backtest.use_fundamentals: false` par défaut : le backtest mesure le score
     technique seul. L'analyse du jour (`cac40_analyzer.py`) utilise toujours les
     fondamentaux, puisqu'il n'y a pas d'anticipation au présent.
  - `backtest.data.period` est câblé. `interval` et `auto_adjust` sont retirés de la
    config : le moteur suppose des données journalières, et les prix ajustés sont
    **nécessaires**, faute de quoi un détachement de dividende ressemblerait à une chute
    de cours et le dividende ne serait jamais crédité.
- **Écarté** :
  - Fondamentaux historiques point-in-time : Yahoo ne les fournit pas gratuitement. Une
    source payante (FactSet, Refinitiv…) serait nécessaire, ce qui dépasse le périmètre.
  - Exécution à la clôture de J+1 plutôt qu'à l'ouverture de J : cela retarde le signal
    d'un jour de plus sans réalisme supplémentaire (un particulier passe ses ordres le
    matin).
- **Conséquences** : le backtest par défaut n'évalue plus la stratégie complète mais sa
  partie technique. C'est le prix d'un chiffre honnête. `use_fundamentals: true` reste
  possible pour comparer, en connaissance du biais, qui est aussi affiché en tête du run.
  Tests : `test_signal_is_unchanged_when_same_day_and_future_data_change` falsifie la
  clôture du jour et le futur, et vérifie que le signal ne bouge pas.

---

## DEC-10 — Actions entières (A4)

- **Contexte** : la quantité achetée valait `budget / prix`, soit des fractions d'action
  (0,97 Safran dans le dernier log). Bourse Direct ne propose pas de fractions : le
  backtest investissait 100 % du budget là où la réalité en laisse une partie en cash, et
  il achetait des titres inaccessibles (1 action Hermès > 2 000 € avec un plafond de 1 000 €).
- **Décision** : `quantité = floor((budget − frais(budget)) / prix)`, avec des frais
  recalculés sur le montant brut réel. Les paliers de frais étant croissants, on a
  `brut + frais(brut) ≤ budget`. Si moins d'une action tient dans le budget, l'achat est
  ignoré et journalisé. `Trade.amount` vaut désormais le **brut** (quantité × prix) et
  `net_cost` le brut + frais : les deux champs ont un sens unique et documenté.
- **Écarté** : autoriser 1 action au-delà du budget quand le cash le permet. Cela
  contournerait la règle de dimensionnement par la confiance et concentrerait le
  portefeuille sur les titres les plus chers.
- **Conséquences** : les titres dont le cours dépasse `max_order_amount` (Hermès…) ne sont
  jamais achetés avec la config actuelle. Relever `max_order_amount` si on veut les inclure.

---

## DEC-11 — Une seule définition du PnL d'un aller-retour (B5)

- **Contexte** : le win rate du résumé comparait la vente **brute** à l'achat frais inclus,
  tandis que le tableau par confiance comparait des montants **nets**. Une même vente
  pouvait donc être un gain dans l'un et une perte dans l'autre.
- **Décision** : `closed_trades()` apparie chaque vente au dernier achat du même titre et
  calcule `PnL = produit net de frais de vente − coût frais d'achat inclus`. Le win rate et
  le résumé par confiance en dérivent tous les deux. Chaque aller-retour porte aussi son
  motif de sortie (`exit_reason`), utilisé par le stop-loss (DEC-12).
- **Justification** : le PnL net est ce qui arrive réellement sur le compte. Un gain brut
  mangé par les frais n'en est pas un.

---

## DEC-12 — Stop-loss (B4)

- **Contexte** : une position ne sortait que sur un signal VENTE (score ≤ −2). Une ligne en
  baisse mais notée NEUTRE pouvait être conservée indéfiniment. Le dernier backtest affiche
  un win rate de 32 % sur les ventes, et la performance venait des positions restées ouvertes.
- **Décision** : `trading.exit_rules.stop_loss_pct: 15`. À chaque rebalance, une position
  dont la clôture de la veille est ≥ 15 % sous son prix d'achat est vendue à l'ouverture,
  avec le motif `STOP-LOSS` tracé dans le trade et dans `closed_trades()`. `null` désactive
  la règle.
- **Justification du seuil** : la volatilité mensuelle d'une grande capitalisation
  française est d'environ 6 à 8 %. 15 % correspond à peu près à 2 écarts-types : la règle ne
  se déclenche pas sur le bruit normal d'un mois, mais coupe les décrochages durables.
  C'est une valeur de départ **à calibrer**, pas un optimum.
- **Écarté** :
  - Un stop intrajournalier (ordre stop permanent) : il faudrait simuler chaque séance
    entre deux rebalances, ce qui ne correspond pas à l'usage réel (revue mensuelle
    manuelle) et complexifie le moteur.
  - Trailing stop et durée maximale de détention : ce sont des règles de gestion
    supplémentaires, à évaluer une fois le backtest de base fiable (YAGNI).
- **Conséquences** : le contrôle réutilise la clôture de la veille et l'ouverture du jour,
  comme les autres ordres. Il ne crée donc pas de nouvelle anticipation.

---

## DEC-13 — Benchmark et métriques de risque (B3)

- **Contexte** : le backtest n'affichait qu'un rendement total, sans point de comparaison,
  ce qui empêchait de savoir si la stratégie apporte quelque chose. La valorisation
  n'était faite qu'aux dates de rebalance (mensuelles) : un drawdown intra-mois restait
  invisible, et le résultat final était figé à la dernière rebalance au lieu de la
  dernière cotation.
- **Décision** :
  - **Benchmark = ETF Amundi CAC 40 (`CAC.PA`)** en achat-conservation : tout le capital à
    l'ouverture de la première séance, parts entières et frais inclus, comme la stratégie.
  - **Pourquoi pas `^FCHI`** : c'est un indice de prix, sans dividendes, alors que la
    stratégie est valorisée en prix ajustés des dividendes. Sur 2024-01 → 2026-09,
    `^FCHI` fait +7,3 % et `CAC.PA` ajusté +16,8 % (mesuré le 2026-09-29). Utiliser l'indice
    aurait flatté la stratégie de ~9,5 points. L'ETF est en outre réellement investissable,
    frais de gestion compris.
  - Boucle de simulation **journalière** : ordres les jours de rebalance, valorisation à
    chaque clôture (`equity_curve`), photo finale à la dernière séance disponible.
  - `performance_metrics()` : rendement total, rendement annualisé, volatilité annualisée
    (√252), Sharpe avec taux sans risque nul, drawdown maximal. Ces métriques sont affichées
    pour la stratégie et le benchmark, et exportées en JSON.
  - `simulate()` est séparée de `run_backtest()` (téléchargement) : la boucle complète est
    testée hors réseau.
- **Écarté** :
  - Un taux sans risque réel (€STR) dans le Sharpe : il faudrait une source de données
    supplémentaire, et le même taux s'appliquerait aux deux colonnes. Pour **comparer**
    la stratégie au benchmark, rf = 0 suffit ; c'est indiqué dans le libellé.
  - Un benchmark équipondéré sur l'univers : plus fidèle au style de la stratégie, mais
    non investissable tel quel. Il pourra être ajouté plus tard.
- **Conséquences** : avec 20 000 € de capital et des ordres de 1 000 € maximum, une large
  part du portefeuille reste en cash. Le benchmark rend ce frein visible : c'est un
  paramètre de dimensionnement à revoir, pas un bug.

---

## DEC-14 — Fin du nettoyage de la config et univers d'actions (C1, C6, B1)

- **C1** : un script compare chaque clé du YAML au code. Restaient inertes :
  `indicators.macd.*` (le MACD utilisait 12/26/9 en dur), désormais câblés, et
  `output.verbose/debug_tickers/save_results`, supprimés : aucun comportement ne les
  justifie. Toutes les clés restantes sont lues, et leur absence lève une erreur (DEC-03).
- **C6** : commentaires corrigés (« Raised from 100 » alors que la valeur valait 100,
  conseils de calibrage parlant de pourcentages d'ordre inexistants, RSI « 50-70 » écrit
  en dur alors que les bornes sont configurables).
- **B1, univers** :
  - Doublon `ELIS.PA` supprimé. Il était sans effet (clé de dict), mais trompeur.
  - `ARRJ.F` (Francfort) remplacé par `MT.AS` (Euronext Amsterdam, cotation principale
    d'ArcelorMittal, en EUR, avec des horaires alignés sur Paris). `MT.PA` n'existe pas
    sur Yahoo (vérifié).
  - **Biais du survivant non corrigé, mais documenté** : la liste est la composition
    actuelle. Les sociétés sorties de la cote ou rétrogradées depuis 2024 manquent, ce qui
    flatte le backtest. Le corriger exige des compositions historiques d'indice (données
    payantes Euronext). Le commentaire en tête de liste et le README le signalent. Le nom
    `NOMS_ENTREPRISES` est conservé pour ne pas multiplier les changements ; le
    commentaire précise qu'il s'agit d'un univers de type SBF 120 et non du CAC 40.
