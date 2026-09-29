# Pistes d'amélioration

Reprend les idées encore pertinentes de l'ancienne roadmap (`DEVELOPMENT.md`,
`BACKTEST_RESULTS.md`), mises à jour après l'audit du 2026-09-29. Par ordre de valeur
estimée.

1. **Calibrage honnête** : maintenant que le backtest est exempt d'anticipation, faire
   varier les seuils `buy`/`sell`, `stop_loss_pct` et le dimensionnement, puis comparer au
   benchmark. Il faut séparer une période d'ajustement et une période de validation, pour
   ne pas sur-ajuster sur 2024-2026.
2. **Confiance anti-prédictive** : sur le run du 2026-09-29, plus la confiance d'achat
   est haute, moins le trade gagne (54 % de trades gagnants entre 0,4 et 0,6 contre 22 %
   au-dessus de 0,8, avec un PnL moyen négatif). Les scores techniques extrêmes
   ressemblent à des sommets de court terme (surachat). Piste : revoir le poids de la
   tendance court terme et de Bollinger, ou plafonner la confiance.
3. **Allocation du capital** : le capital est investi dès le 6e mois et 404 signaux
   d'achat sont ensuite rejetés faute de cash. Envisager une rotation (vendre la ligne la
   plus faible pour financer un signal plus fort) ou un nombre maximal de lignes.
4. **Fondamentaux historiques** : une source point-in-time permettrait de backtester la
   stratégie complète (`use_fundamentals: true` sans biais).
5. **Univers historique** : utiliser des compositions d'indice datées pour supprimer le
   biais du survivant.
6. **Cache disque des cotations** : utile pour itérer vite sur le calibrage.
7. **Qualité du dividende** : taux de distribution, détection des pièges à rendement.
8. **Risque de portefeuille** : limite par secteur, corrélation, trailing stop.
