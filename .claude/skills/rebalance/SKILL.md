---
name: rebalance
description: Routine mensuelle d'investissement. Lit le dernier export de positions Bourse Direct du dossier Téléchargements, lance l'analyse du jour et produit le résumé de quoi vendre et quoi acheter selon la stratégie testée. À utiliser quand l'utilisateur demande quoi acheter / vendre, son rebalance, ou fournit un export de positions.
argument-hint: "[espèces disponibles en € par compte]"
---

# Rebalance mensuel

Objectif : transformer les positions réelles de l'utilisateur en une liste d'ordres conforme
à la stratégie backtestée (règles dans `CLAUDE.md` et `docs/DECISIONS.md`, DEC-25).
**Tous les chiffres viennent de `src/rebalance.py`** : ne jamais recalculer, arrondir
autrement ou modifier une règle à la main.

## 1. Trouver les exports de positions

- Dossier : `~/Downloads` (`C:\Users\<utilisateur>\Downloads`).
- Nom : `<n° de compte>EUR-JJ_MM_AAAA HH_MM_SS.xlsx`, par exemple
  `…EUR-29_09_2026 16_32_37.xlsx` pour un export du 29/09/2026 à 16:32:37.
- L'utilisateur peut avoir **plusieurs comptes** (PEA, compte-titres) : la correspondance
  n° de compte → compte est dans `CLAUDE.local.md` (non versionné, ne jamais la recopier
  ailleurs).
- Sélection, **faite par le script** (ne pas la refaire à la main) :

  ```bash
  PYTHONIOENCODING=utf-8 python src/rebalance.py --list-exports
  ```

  Règle : on prend la **date la plus récente** parmi tous les exports, puis, pour chaque
  compte ayant un export **ce jour-là**, son export le plus récent. Un compte dont le
  dernier export est plus ancien **n'est pas traité**, même s'il a un export à une date
  antérieure. Exemple : PEA exporté le 1er octobre, CTO exporté le 1er et le 2 octobre →
  rebalance du **CTO seul**, sur son export du 2 octobre.
- Annoncer les fichiers retenus (nom du compte et date). Si un compte est écarté, le dire.
- Si la date retenue est antérieure à aujourd'hui, le signaler et proposer de retélécharger
  les exports avant de continuer (les positions ont pu changer).

## 2. Obtenir les espèces disponibles

L'export ne contient pas le solde en espèces. Il faut **un montant par compte retenu**.
Utiliser l'argument du skill s'il les fournit sans ambiguïté, sinon **les demander**
(Bourse Direct : « Espèces disponibles »). Ne jamais les supposer.

## 3. Lancer le plan, une fois par compte

```bash
PYTHONIOENCODING=utf-8 python src/rebalance.py --cash <montant du compte> --export "<chemin de l'export>"
```

Durée ~1 à 2 min par compte (analyse des ~96 valeurs). Chaque compte est une enveloppe
distincte : son plan ne dépend que de ses positions et de ses espèces. Le plan est aussi
écrit dans `journal/AAAA-MM-JJ_<n° de compte>.md`, local et non versionné : c'est la base
du suivi réel face à l'ETF.

## 4. Présenter le résumé

Un bloc par compte (titré PEA / CTO), chacun dans cet ordre, de façon concise :

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
