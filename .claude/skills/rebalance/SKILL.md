---
name: rebalance
description: Routine mensuelle d'investissement. Lit le dernier export de positions Bourse Direct du dossier Téléchargements, lance l'analyse du jour et produit le résumé de quoi vendre et quoi acheter selon la stratégie testée. À utiliser quand l'utilisateur demande quoi acheter / vendre, son rebalance, ou fournit un export de positions.
argument-hint: "[espèces disponibles en €]"
---

# Rebalance mensuel

Objectif : transformer les positions réelles de l'utilisateur en une liste d'ordres conforme
à la stratégie backtestée (règles dans `CLAUDE.md` et `docs/DECISIONS.md`, DEC-25).
**Tous les chiffres viennent de `src/rebalance.py`** : ne jamais recalculer, arrondir
autrement ou modifier une règle à la main.

## 1. Trouver l'export de positions

- Dossier : `~/Downloads` (`C:\Users\<utilisateur>\Downloads`).
- Nom : `<n° de compte>EUR-JJ_MM_AAAA HH_MM_SS.xlsx`, par exemple
  `…EUR-29_09_2026 16_32_37.xlsx` pour un export du 29/09/2026 à 16:32:37.
- Prendre le **plus récent d'après la date du nom** (le script le fait par défaut).
  Annoncer le fichier retenu et sa date.
- S'il date d'avant aujourd'hui, le signaler et proposer de retélécharger l'export avant
  de continuer (les positions ont pu changer).

## 2. Obtenir les espèces disponibles

L'export ne contient pas le solde en espèces. Utiliser l'argument du skill s'il est fourni,
sinon **demander le montant** (Bourse Direct : « Espèces disponibles »). Ne jamais le
supposer.

## 3. Lancer le plan

```bash
PYTHONIOENCODING=utf-8 python src/rebalance.py --cash <montant> --export "<chemin de l'export>"
```

Durée ~1 à 2 min (analyse des ~96 valeurs). Le plan est aussi écrit dans
`journal/AAAA-MM-JJ.md`, local et non versionné : c'est la base du suivi réel face à l'ETF.

## 4. Présenter le résumé

Dans cet ordre, de façon concise :

1. **Avertissements** du script en premier, notamment « marché ouvert ». La stratégie décide
   sur la clôture de la veille et s'applique le **1er jour de bourse du mois, avant 9 h** :
   si ce n'est pas le cas, le dire.
2. **À vendre** : titre, quantité, motif (signal VENTE ou stop-loss), produit estimé.
3. **À acheter**, dans l'ordre de priorité : titre, quantité, montant frais inclus.
   Mentionner les ACHAT non servis faute de cash.
4. **À conserver**, puis **hors stratégie** : ces lignes relèvent de la décision de
   l'utilisateur, le programme ne les juge pas.
5. **Trésorerie** finale, et rappel que l'exécution se fait au cours d'ouverture.

Ne pas ajouter d'opinion de marché ni de titre absent du plan. Si l'utilisateur veut
écarter un titre (par exemple pour une raison fondamentale), le noter comme choix manuel.
