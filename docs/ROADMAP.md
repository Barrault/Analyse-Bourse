# Pistes d'amélioration

Reprend les idées encore pertinentes de l'ancienne roadmap (`DEVELOPMENT.md`,
`BACKTEST_RESULTS.md`), mises à jour après l'audit du 2026-09-29. Par ordre de valeur
estimée.

1. **Calibrage honnête** : maintenant que le backtest est exempt d'anticipation, faire
   varier les seuils `buy`/`sell`, `stop_loss_pct` et le dimensionnement, puis comparer au
   benchmark. Il faut séparer une période d'ajustement et une période de validation, pour
   ne pas sur-ajuster sur 2024-2026.
2. **Confiance sans pouvoir prédictif** (étude du 2026-09-29, backtest technique seul).
   Le tableau « PnL par confiance » du backtest suggère un fort effet inverse (54 %
   de trades gagnants entre 0,4 et 0,6, contre 22 % au-dessus de 0,8). Mais il ne compte
   que les trades clôturés, avec ~28 trades par tranche. Mesuré sur les **1 283 signaux
   ACHAT** (exécutés ou non), à partir de l'ouverture du jour du signal :
   - à 3 mois, les tranches ne se distinguent pas (+3,6 % / +3,8 % / +2,6 %, ~53 % de
     gagnants partout ; écart haute − basse −1,0 pt, IC 95 % [−4,6 ; +2,3]) ;
   - à 1 mois, léger retard de la tranche haute (−2,3 pts, IC 95 % [−4,3 ; −0,4]),
     cohérent avec un peu plus de surachat au signal (RSI 62 contre 57, 14 % des cas
     au-dessus de la bande de Bollinger haute contre 6 %) ;
   - la corrélation de rang entre confiance et rendement est quasi nulle (−0,02 à 3 mois).
   Conséquence : dimensionner les ordres selon la confiance (100 € → 1 000 €) ne repose sur
   rien de mesurable. À tester : des montants égaux, et une confiance recalibrée
   (poids de Bollinger « au-dessus de la bande haute », seuil de surachat du RSI).
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
