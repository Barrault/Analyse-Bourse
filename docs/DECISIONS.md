# Journal des décisions

Chaque entrée répond à un constat de [AUDIT.md](AUDIT.md) : **contexte → décision →
alternatives écartées → conséquences**. Les entrées sont ajoutées au fil des commits
de la branche `fix/audit-corrections`.

---

## DEC-00 — Organisation du travail git

- **Contexte** : ~30 constats touchant surtout 3 fichiers (`cac40_analyzer.py`, `backtest.py`, `config.yaml`).
- **Décision** : une seule branche `fix/audit-corrections` partant de `master`, un commit
  atomique par constat ou groupe de constats liés (format *Conventional Commits*,
  identifiant d'audit dans le message), puis fusion en *fast-forward* dans `master`.
  Projet mené seul : pas de Pull Request, la branche sert à isoler le travail en cours et
  est supprimée après fusion.
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
- **Correctif ultérieur** : le premier commit de cette décision laissait l'écriture du JSON
  sur les anciennes variables (`NameError` en fin de run). Le script de modification
  n'avait pas vérifié que son remplacement avait eu lieu, et aucun test ne couvrait
  l'export. Le problème a été détecté en lançant le vrai backtest de bout en bout. Depuis :
  `build_results()` et `save_results()` sont des fonctions testées
  (`tests/test_run_full_backtest.py`), et toute exception est tracée dans le journal avant
  la restauration de stderr.

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
- **Conséquences** : la comparaison au benchmark devient la mesure de référence de tout
  futur calibrage. *Correction* : une première version de ce paragraphe annonçait un
  capital largement laissé en cash. C'était une extrapolation depuis un test synthétique à
  3 titres. Sur l'univers réel, le capital est investi dès le 6e mois (environ 200 € de
  cash, 35 à 40 lignes) et 404 signaux d'achat sont rejetés faute de trésorerie (run du
  2026-09-29).

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

---

## DEC-15 — Intégration continue

- **Décision** : workflow GitHub Actions `tests.yml` qui lance `pytest` (hors réseau) sur
  chaque PR et chaque push sur `master`, en Python 3.10, la version utilisée localement
  et le minimum déclaré dans `pyproject.toml`.
- **Justification** : les corrections de cette branche reposent sur des tests de
  non-régression (anticipation, frais, PnL). Sans exécution automatique, ils cesseraient
  vite d'être lancés. Les tests réseau restent manuels (`pytest -m network`), car Yahoo
  n'est pas une dépendance fiable en CI.
- **Écarté** : une matrice multi-versions et un linter. Pour un projet personnel à un seul
  interpréteur, cela ajouterait du bruit sans bénéfice.

---

## DEC-16 — Documentation (D1, D4)

- **Contexte** : le README décrivait un état révolu (fichier `quick_backtest.py`
  inexistant, dépendance `ta` inutile, seuils ±3, capital de 5 000 €) ; quatre fichiers
  (`DEVELOPMENT.md`, `FEATURE_CONFIG.md`, `INTEGRATION_COMPLETE.md`,
  `BACKTEST_RESULTS.md`) étaient des comptes rendus d'étape datés, qui se contredisaient
  entre eux et contredisaient le code.
- **Décision** : un README décrivant l'état **actuel** (installation, usage, méthode,
  limites, tests) ; les pistes encore valables des anciennes roadmaps, réécrites avec les
  constats du run réel, dans `docs/ROADMAP.md` ; un `CHANGELOG.md` ; suppression des
  quatre fichiers, qui restent consultables dans l'historique git.
- **Écarté** : mettre ces fichiers à jour un par un. Leur contenu relève de l'historique
  (ce qui a été fait, quand), ce que git et le CHANGELOG couvrent mieux. Les maintenir
  reproduirait la même dérive.
- **Principe retenu** : la documentation décrit ce qui **est** (README), ce qui a été
  **décidé et pourquoi** (DECISIONS), ce qui **pourrait venir** (ROADMAP). Les résultats
  chiffrés, qui changent à chaque run, vivent dans les sorties du backtest et le CHANGELOG,
  pas dans le README.

---

## DEC-17 — Contrôle qualité des cours : sauts aberrants

- **Contexte** : l'étude des composantes du score (2026-09-29) a mis au jour des cours
  Yahoo corrompus. Atos passe de 48,5 € à 4 187 € le 2024-11-12 (regroupement d'actions
  non ajusté), puis revient à 26 € le 2024-12-06. Vivendi chute de 78 % le 2024-12-09, jour
  de sa scission en quatre sociétés, non ajustée : l'actionnaire n'a rien perdu, il a reçu
  des titres. Ces sauts faussent les moyennes mobiles, fabriquent des gains ou des pertes
  fictifs, et dominent toute moyenne statistique.
- **Détection** : une clôture multipliée ou divisée par au moins `max_daily_factor = 2` en
  une séance. Sur 10 ans et 96 titres, 4 titres sont concernés : Atos et Vivendi
  (aberrants), Eutelsat (+120 % le 2025-03-05) et Worldline (−59 % le 2023-10-25), deux vrais
  mouvements de marché vérifiés et listés dans `data_quality.verified_real_moves`.
- **Décision** :
  - Les indicateurs sont calculés **par segment** entre deux sauts : aucune moyenne mobile
    ne mélange deux échelles de prix. Un segment de moins de 200 séances ne produit pas de
    signal.
  - Une position détenue le jour d'un saut est soldée au **dernier cours valide** (clôture
    de la veille), avec le motif `OST` (opération sur titre).
  - Pas de signal quand un saut sépare la séance du signal de celle de l'exécution.
  - L'analyse du jour n'utilise que le segment en cours.
- **Écarté** :
  - *Tronquer l'historique avant le dernier saut* : c'était ma première implémentation. Un
    test de non-anticipation l'a fait échouer, et à raison. Tronquer selon le **dernier**
    saut, c'est savoir en 2023 qu'Atos aura un problème de données fin 2024, et donc
    l'exclure d'avance. Comme Atos s'est effondrée en 2024, cela aurait flatté le backtest.
    Le découpage par segment n'utilise que le passé.
  - *Corriger les cours* (réappliquer le ratio du regroupement) : il faudrait connaître
    chaque opération sur titre et son ratio, donc maintenir des données à la main.
  - *Exclure les titres concernés* : même biais que la troncature.
- **Conséquences** : Atos et Vivendi ne sont plus analysables pendant les 200 séances qui
  suivent leur saut. Tout nouveau saut détecté est signalé au chargement pour vérification
  manuelle : s'il est réel, il faut l'ajouter à la liste blanche.

---

## DEC-18 — Protocole de calibrage : apprentissage et test séparés, historique de 10 ans

- **Contexte** : l'étude du 2026-09-29 montrait que la confiance ne prédit rien et que
  plusieurs composantes du score n'ont aucun effet. Mais elle portait sur 2024-2026.
  Régler le score sur cette période puis l'y évaluer donnerait un résultat flatté
  (sur-ajustement : on retrouve ce qu'on a appris).
- **Décision** :
  - Historique porté à **10 ans** (`backtest.data.period: 10y`, données dès 2016-09).
  - **Apprentissage** (`calibration.train_start/train_end`) : 2017-07 → 2021-09. Tous les
    réglages (composantes, table de confiance) sont décidés sur cette période uniquement.
    Le début laisse 200 séances d'historique pour la SMA200. La fin est **purgée** de
    3 mois, pour que le dernier rendement mesuré se termine avant la période de test.
  - **Test** (`backtest.start_date`) : 2022-01 → aujourd'hui. Il inclut la baisse de 2022,
    que 2024-2026 ne contenait pas. On y évalue, on n'y règle rien.
  - Mesure : rendement relatif à l'ETF CAC 40 sur 63 séances (~3 mois), de l'ouverture du
    jour du signal à la clôture de fin d'horizon. Pour les écarts entre composantes, on
    utilise son **rang percentile dans le mois**, robuste aux extrêmes, et un t de Student
    calculé **sur les mois** (les titres d'un même mois ne sont pas indépendants).
  - **Règle de sélection fixée avant de voir les résultats** (`calibration.min_t: 1.0`) :
    une composante garde son poids si son effet a le signe attendu et un t ≥ 1 ; sinon son
    poids passe à 0. On ne **renverse** jamais un signe et on n'optimise pas la valeur des
    poids : avec ~50 mois, optimiser, c'est sur-ajuster.
  - Outil reproductible : `src/calibrate.py` (`features`, `calibrate`, `evaluate`), testé.
- **Écarté** :
  - Une régression pour estimer les poids : trop de degrés de liberté pour 50 mois, et
    des poids difficiles à expliquer.
  - Une validation glissante (*walk-forward*) sur plusieurs fenêtres : plus robuste, mais
    elle demande de recalibrer à chaque fenêtre. Une seule séparation apprentissage/test,
    avec un test qui contient une baisse, suffit pour ce projet.
- **Limites** : sur 10 ans, le biais du survivant est plus fort (univers actuel). Six
  titres sont cotés après 2017 et n'entrent dans les données qu'à leur introduction.

---

## DEC-19 — Sélection des composantes techniques

- **Contexte** : application de la règle de DEC-18 sur l'apprentissage 2017-07 → 2021-09
  (4 538 observations, 50 mois ; sortie de `python src/calibrate.py features`).

  | Composante | Poids | Écart de rang | t | Décision |
  |---|---:|---:|---:|---|
  | Cours > SMA200 | ±2,0 | +4,6 | 3,1 | garder |
  | SMA50 > SMA200 | ±1,2 | +4,2 | 2,4 | garder |
  | SMA20 > SMA50 | ±1,0 | +2,4 | 1,9 | garder |
  | MACD > 0 | ±1,8 | +2,5 | 2,1 | garder |
  | Histogramme MACD > 0 | ±1,5 | −0,4 | −0,3 | 0 |
  | RSI zone neutre | +0,5 | +0,4 | 0,4 | 0 |
  | RSI survente | +1,0 | +0,9 | 0,4 | 0 |
  | RSI surachat | −1,5 | +2,1 | 0,7 | 0 (signe contraire) |
  | Au-dessus de la bande de Bollinger haute | +0,8 | −2,1 | −1,1 | 0 (signe contraire) |
  | Sous la bande de Bollinger basse | −1,5 | +4,0 | 1,3 | 0 (signe contraire) |
  | Volume > moyenne | ±0,5 | +1,9 | 1,8 | garder |
  | Volatilité faible | ±0,8 | +3,3 | 0,9 | 0 |

- **Décision** : poids mis à 0 dans `config.yaml`. Chaque ligne est commentée avec son écart
  et son t, pour garder la trace du pourquoi. Une composante de poids nul n'affiche plus de
  motif : écrire « RSI haut : risque de correction » alors que la règle n'a aucun effet
  mesuré induirait l'utilisateur en erreur. Le motif « Volume faible » est reformulé
  (« le mouvement manque de soutien ») pour correspondre à sa contribution négative.
- **Cohérence** : ces conclusions rejoignent l'étude exploratoire faite sur 2024-2026, que
  cette décision **n'a pas utilisée**. Deux périodes distinctes pointent dans le même sens :
  seules la tendance et le momentum portent l'information, conformément à l'effet momentum
  documenté en finance. Seule divergence : le volume, gardé ici (t = 1,8), était neutre sur
  2024-2026.
- **Écarté** : inverser les signes contraires (RSI > 70 en bonus, par exemple). Les t
  (0,7 à 1,3) ne le justifient pas, et ce serait une optimisation sur l'échantillon.
- **Conséquences** : le score technique va désormais de −6,5 à +6,5. Les seuils (achat 4,
  vente −2) sont conservés : un ACHAT exige des tendances long et moyen terme haussières.

---

## DEC-20 — Confiance = probabilité calibrée de battre le CAC 40

- **Contexte** : la confiance était la distance du score au seuil, mise à l'échelle
  (DEC-07), puis modifiée par des plafonds fondamentaux arbitraires (0,40, 0,90, 0,35,
  0,30). Aucune de ces valeurs n'avait été mesurée. Résultat : une confiance de 0,82 ne
  prédisait rien (étude du 2026-09-29).
- **Décision** :
  - **Confiance = probabilité historique que la recommandation soit dans le bon sens** :
    `p` = part des titres ayant battu l'ETF CAC 40 à 3 mois dans la même tranche de score
    technique, sur l'apprentissage. Confiance = `p` pour un ACHAT ou un NEUTRE, `1 − p`
    pour une VENTE. La table (`scoring.confidence_calibration`) est produite par
    `python src/calibrate.py calibrate`, en 5 tranches de score (quantiles), lissée par
    **régression isotone** : un score plus haut n'a jamais une probabilité plus basse,
    ce qui évite d'interpréter le bruit d'échantillonnage.
  - Seul le **score technique** est calibré : il n'existe pas de fondamentaux historiques
    pour mesurer l'effet des autres. Les fondamentaux continuent de déplacer le score
    total, donc la recommandation, mais plus la confiance.
  - Les plafonds fondamentaux sont supprimés. Leurs messages (pertes, Value Support, Panic
    Sell, profil spéculatif) restent affichés comme **alertes**, sans effet chiffré.
  - Chaque analyse affiche la probabilité et la moyenne de référence, par exemple :
    « 49 % des titres à ce niveau de score ont battu le CAC 40 à 3 mois (moyenne : 47 %) ».
  - Backtest : achats triés par probabilité puis par score technique (la table est par
    tranches, donc les ex-aequo sont nombreux) ; tableau PnL par valeur de probabilité.
- **Résultat du calibrage** : la probabilité va de **43,7 % à 49,3 %**, pour une moyenne de
  47,0 %. La moyenne est sous 50 % car l'indice est tiré par quelques fortes hausses : le
  titre médian fait moins bien que lui. L'avantage du score est **réel mais modeste**, et
  la confiance le dit désormais, au lieu d'afficher 82 %.
- **Écarté** :
  - Une régression logistique sur le score : même idée, mais elle impose une forme en S que
    rien ne justifie. Les tranches plus la régression isotone ne supposent rien.
  - Calibrer la probabilité de **rendement positif** : elle mesurerait surtout la hausse
    générale du marché, pas la qualité du choix d'un titre. Or c'est le choix des titres
    qui compte quand le capital est entièrement investi.

---

## DEC-21 — Montant identique pour chaque achat

- **Contexte** : le montant variait de 100 à 1 000 € selon la confiance (DEC-07). Or la
  confiance calibrée va de 44 % à 49 % (DEC-20) : moduler le montant revenait à miser
  davantage sur des signaux à peine différents, sans avantage mesuré.
- **Décision** : `trading.order_amount: 1000` pour tout achat. `min_order_amount` devient
  le plancher d'un achat réduit quand la trésorerie ne permet pas le montant plein. La
  confiance sert désormais à **ordonner** les achats quand le cash manque (DEC-20), pas à
  les dimensionner. Clés supprimées : `max_order_amount` et
  `order_sizing.min/max_confidence_*` ; `margin_buffer` passe directement sous `trading`.
- **Justification** : à avantage égal, des lignes de même taille minimisent le risque de
  concentration. C'est l'approche par défaut tant qu'aucune mesure ne justifie autre chose.
- **Écarté** : un dimensionnement de type Kelly, proportionnel à l'avantage. Avec un
  avantage de 1 à 2 points de probabilité, estimé avec incertitude, il serait quasi nul
  et très instable.

---

## DEC-22 — Évaluation hors échantillon (2022-01 → 2026-09)

Période de test jamais utilisée pour un réglage (DEC-18). Elle inclut la baisse de 2022.
Fondamentaux désactivés, capital de 20 000 €, runs du 2026-09-29.

### Fiabilité de la confiance (`python src/calibrate.py evaluate`, 5 220 observations)

| Tranche de score | n | Probabilité prévue | Fréquence observée |
|---|---:|---:|---:|
| < −5,5 | 516 | 43,7 % | 48,1 % |
| −5,5 à −0,1 | 1 633 | 43,7 % | 43,2 % |
| −0,1 à 3,5 | 1 120 | 48,2 % | 48,0 % |
| 3,5 à 5,5 | 460 | 49,3 % | 50,4 % |
| ≥ 5,5 | 1 491 | 49,3 % | 48,5 % |

- Moyenne de référence stable (46,9 % en test contre 47,0 % en apprentissage). Quatre
  tranches sur cinq tombent à ±1 point de la prévision.
- Exception : la tranche la plus baissière a davantage rebondi que prévu (48,1 % contre
  43,7 %). Les titres les plus massacrés ont rebondi, notamment après 2022.
- L'avantage reste **faible** : corrélation de rang score/rendement de +0,04, tranche haute
  à +1,9 point de rang (t = 1,5, non significatif seul). Il va dans le sens prévu, mais ce
  n'est pas une machine à surperformer.

### Backtest sur la période de test

| | Ancienne version (`master`) | Nouveau code, anciens poids | **Nouvelle version** | ETF CAC 40 |
|---|---:|---:|---:|---:|
| Rendement total | +19,0 % | +18,7 % | **+46,2 %** | +29,6 % |
| Rendement annualisé | 3,7 % | 3,7 % | **8,4 %** | 5,6 % |
| Volatilité | 14,3 % | 14,6 % | 16,0 % | 16,3 % |
| Sharpe (rf = 0) | 0,33 | 0,32 | **0,57** | 0,41 |
| Drawdown max | −23,3 % | −25,0 % | −20,9 % | −20,9 % |

- **L'ancienne version fait moins bien que l'ETF sur 2022-2026.** Son +37 % sur 2024-2026
  (CHANGELOG 1.1.0) tenait donc largement à la période choisie.
- **Ablation** : le nouveau code avec les anciens poids donne le même résultat que
  l'ancienne version. Le gain vient donc presque entièrement de la **sélection des
  composantes** (DEC-19). La confiance calibrée et les montants égaux rendent l'outil plus
  honnête sans changer le rendement.
- Tous les achats du test tombent dans la tranche haute (49,3 %) : le seuil d'achat
  (score ≥ 4) sélectionne déjà la meilleure tranche. Les achats sont départagés par le
  score technique.
- L'ancienne version n'a détenu ni Atos ni Vivendi au moment de leurs sauts de cours. Le
  contrôle qualité (DEC-17) ne contribue donc pas à l'écart.

### Réserves

- **Un seul chemin historique** (57 mois) : +2,7 points par an d'écart avec l'ETF, c'est
  encourageant mais compatible avec de la chance. Le t de la tranche haute (1,5) invite à
  la prudence.
- **Biais du survivant** : l'univers est la composition actuelle, sur 10 ans. Il flatte la
  stratégie mais pas l'ETF, qui contient les sortants : la comparaison est biaisée en
  faveur de la stratégie.
- **Degré de liberté du chercheur** : l'idée de retirer des composantes est née d'une
  étude exploratoire sur 2024-2026, qui fait partie du test. La décision elle-même repose
  sur une règle fixée à l'avance et appliquée à l'apprentissage seul, mais l'intention
  préexistait.
- La mesure porte sur la partie **technique** : l'effet des fondamentaux sur la
  recommandation reste non mesuré.

### Décision

Fusion dans `master`. La nouvelle version est à la fois plus honnête (confiance mesurée,
données contrôlées) et meilleure hors échantillon. Prochaine étape recommandée : suivre
l'écart avec l'ETF en conditions réelles avant d'engager davantage de capital.

---

## DEC-23 — Test du rendement du dividende : écarté (effet instable)

- **Contexte** : les fondamentaux n'ont pas d'historique gratuit, sauf les dividendes
  versés. Avec les cours bruts, on peut reconstituer le rendement sur 12 mois glissants
  tel qu'il était connu à chaque date. C'est le seul critère « value » testable.
- **Méthode** : `python src/calibrate.py dividend`. On compare le tiers des titres au plus
  fort rendement au reste, en rang du rendement relatif à 3 mois, avec la règle de DEC-18
  fixée à l'avance (bon signe et t ≥ 1 sur l'apprentissage).
- **Résultat** :

  | Période | Tiers au plus fort dividende vs reste | Parmi les ACHAT (moitié haute vs basse) |
  |---|---:|---:|
  | Apprentissage 2017-07 → 2021-09 | −1,9 (t = −1,5) | −2,0 (t = −1,2) |
  | Test 2022-01 → 2026-09 | +5,5 (t = 5,2) | +4,6 (t = 2,5) |

- **Décision** : **écarté**, conformément à la règle. L'effet s'inverse d'une période à
  l'autre. Le dividende a sous-performé dans la décennie de taux bas, puis fortement
  surperformé depuis la remontée des taux de 2022. C'est le comportement connu du facteur
  « value » (sa « décennie perdue » des années 2010, puis son rebond).
- **Pourquoi ne pas le garder malgré le test favorable** : ce serait choisir en regardant
  la période de test, c'est-à-dire exactement le biais que le protocole doit empêcher. Le
  test montre surtout que ce critère **dépend du régime de marché**. Le garder reviendrait
  à parier que le régime de 2022-2026 va durer.
- **Conséquence pour E/P et B/P** : ils relèvent du même facteur « value » et ne sont pas
  testables. Si le seul représentant mesurable est instable, rien ne justifie de leur donner
  un rôle dans la décision, même comme simple départage. Le score composite « value »
  envisagé n'est donc pas construit (DEC-24).

---

## DEC-24 — Décision sur le score technique seul ; fondamentaux en information et en filtre

- **Contexte** :
  - L'analyse du jour ajoutait ~10 règles fondamentales au score, avec des poids fixés à la
    main (−2 pour un PE > 22, +1,5 pour une décote…). Elle ne suivait donc pas la stratégie
    mesurée par le backtest (technique seule). Le 2026-09-29, elle transformait 7 ACHAT
    techniques en NEUTRE sans qu'on sache si c'était utile.
  - Ces règles ne sont pas testables (pas d'historique gratuit), et le seul fondamental
    testable, le dividende, a un effet instable (DEC-23).
- **Décision**, alignée sur les pratiques recommandées quand un signal n'est pas mesurable
  (poids égaux ou nuls plutôt que des poids « à l'intuition », filtres plutôt que poids,
  influence plafonnée) :
  1. **La recommandation ne dépend que du score technique.** L'analyse du jour applique
     désormais exactement la stratégie évaluée hors échantillon (DEC-22).
  2. **Un seul filtre fondamental** (`fundamentals.exclude_loss_making: true`) : un ACHAT
     sur une entreprise en perte (BPA < 0) devient NEUTRE. C'est un filtre de prudence
     plutôt qu'un pari de rendement. Il est cohérent avec le facteur « rentabilité »
     documenté en finance (les entreprises non rentables ont eu des rendements moyens plus
     faibles), et son pire effet est de rater quelques rebonds. Il est désactivable.
  3. **PE, P/B et dividende affichés pour information** sur une ligne, pour garder
     l'utilisateur maître d'un veto manuel.
  4. Suppression de `scoring.fundamentals` (poids, tranches, seuils) et des alertes Value
     Support / Panic Sell qui en dépendaient.
- **Écarté** :
  - *Score composite « value »* (rangs E/P, B/P et dividende au sein du secteur, pour
    départager les ACHAT) : c'était ma recommandation initiale, mais le test du dividende
    (DEC-23) montre que ce facteur a changé de sens entre 2017-2021 et 2022-2026. Même
    réduit à un simple départage, l'introduire reviendrait à parier sur le régime de marché
    actuel, sans mesure pour le justifier.
  - *Garder les anciennes règles en les « adoucissant »* : ce serait toujours des poids
    arbitraires, simplement plus petits.
- **Conséquences** :
  - Le backtest est inchangé (il n'utilisait déjà que le technique), sauf si
    `use_fundamentals: true` : dans ce cas, le filtre s'applique avec les BPA actuels, ce
    qui introduit un biais d'anticipation, signalé en tête du run.
  - Le 2026-09-29, l'analyse du jour donne 14 ACHAT : les 15 signaux techniques, moins
    North Atlantic Energies (en perte).
- **Seul le filtre « perte » n'est pas vérifié par les données** : il faudra le juger à
  l'usage, en suivi réel.

---

## DEC-25 — Routine mensuelle outillée : script de rebalance, skill et hooks

- **Contexte** : le suivi en conditions réelles est la priorité n°1 de la roadmap. Chaque
  mois, il faut appliquer à la main des règles précises (vente sur signal ou stop-loss,
  priorité des achats, actions entières, frais, réserve de trésorerie). C'est source
  d'erreurs, et rien ne gardait la trace des décisions.
- **Décision** :
  - `src/rebalance.py` lit l'export de positions Bourse Direct, retrouve les tickers par
    ISIN (recherche Yahoo, préférence pour la cotation `.PA`), relance l'analyse du jour et
    applique **les mêmes règles que le backtest**. Le plan est écrit dans `journal/`.
  - Skill `/rebalance` : il **orchestre et présente**, sans calculer. Les chiffres viennent
    du script testé : plus fiable, et moins coûteux qu'un calcul fait par le modèle.
  - Hooks `PreToolUse` sur Bash : tests avant commit, `git add` global bloqué. Ce sont des
    garde-fous déterministes, sans coût de contexte, qui ne dépendent pas de la mémoire de
    l'assistant.
- **Détails et justifications** :
  - L'export est au format *Strict OOXML*, que `openpyxl` ne lit pas. Il est lu directement
    (zip + XML, bibliothèque standard) : **aucune nouvelle dépendance**.
  - L'export le plus récent est choisi d'après la **date de son nom**, pas la date de
    modification du fichier, qui change en cas de copie.
  - L'export ne contient pas les espèces : elles sont passées en paramètre (`--cash`),
    jamais supposées.
  - Stop-loss comparé au **PRU du courtier** (frais d'achat inclus), donc légèrement plus
    prudent que le backtest, qui utilise le prix d'exécution.
  - Un titre hors univers (l'ETF levier) ou sans signal est listé « décision manuelle ».
  - Un ACHAT sur un titre **déjà détenu** n'est pas racheté, comme dans le backtest.
- **Confidentialité** : le numéro de compte n'apparaît ni dans le code ni dans le skill
  (motif générique `…EUR-JJ_MM_AAAA HH_MM_SS.xlsx`), et `journal/` est ignoré par git :
  positions et montants restent locaux.
- **Écarté** :
  - Parser l'export dans le skill, en langage naturel : non testable et non reproductible.
  - Un MCP ou une API courtier : Bourse Direct n'en propose pas.

## DEC-26 — Rebalance sur plusieurs comptes : une seule date d'export

- **Contexte** : l'utilisateur a deux comptes (PEA et compte-titres), chacun avec son
  export de positions. Le script ne retenait qu'un fichier, le plus récent tous comptes
  confondus, et deux plans du même jour s'écrasaient dans `journal/`.
- **Décision** :
  - `find_latest_exports` retient la **date la plus récente** parmi tous les exports, puis
    l'export le plus récent de **chaque compte ayant un export ce jour-là**. Un compte dont
    le dernier export est plus ancien n'est pas traité (PEA au 1er octobre, CTO au 1er et
    au 2 → CTO seul, au 2).
  - Un plan par compte (`--export`, `--cash` du compte), journal nommé par compte.
  - Sans `--export`, le script refuse de choisir entre plusieurs comptes.
- **Justification** : un plan repose sur les positions du moment. Traiter un compte sur un
  export plus ancien reviendrait à décider sur des positions peut-être périmées ; l'absence
  d'export frais signale que ce compte n'est pas à rebalancer ce jour-là.
- **Confidentialité** : la correspondance n° de compte → PEA / CTO est dans
  `CLAUDE.local.md`, ignoré par git. Le code ne connaît que le motif générique.
- **Écarté** :
  - Prendre le dernier export de chaque compte, quelle que soit sa date : mélange des
    positions de dates différentes.
  - Un plan unique fusionnant les comptes : les enveloppes fiscales sont distinctes et la
    stratégie backtestée porte sur un seul portefeuille.
