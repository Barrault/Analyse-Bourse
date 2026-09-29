# Pistes d'amélioration

Mises à jour après la version 1.3.0 (2026-09-29). Par ordre de valeur estimée.

1. **Suivi en conditions réelles** : noter chaque mois les recommandations suivies et
   comparer à l'ETF CAC 40. C'est le seul test qui ne souffre d'aucun biais de backtest.
2. **Validation glissante** (*walk-forward*) : recalibrer sur des fenêtres successives
   pour vérifier que la sélection des composantes (DEC-19) est stable dans le temps, et
   pas propre à 2017-2021.
3. **Valeurs des poids** : seule leur sélection est mesurée. Tester des poids égaux pour
   les composantes gardées : plus simple, et souvent aussi robuste.
4. **Tranche très baissière** : sur le test, les titres au score le plus bas ont plus
   rebondi que prévu (48 % contre 44 %). À surveiller avant d'en faire une règle
   (effet de retour à la moyenne ?).
5. **Allocation du capital** : le capital est investi en quelques mois, puis la plupart
   des signaux sont rejetés faute de cash. Envisager une rotation (vendre la ligne la plus
   faible pour un signal nettement meilleur) ou un nombre maximal de lignes.
6. **Fondamentaux historiques** : une source point-in-time permettrait de tester E/P et
   B/P, et de revoir DEC-24. Le dividende montre que le facteur « value » dépend du régime
   de taux (DEC-23) : il faudrait le tester sur plusieurs cycles, pas une seule période.
   Le filtre « entreprise en perte » est à juger en suivi réel.
7. **Univers historique** : utiliser des compositions d'indice datées pour supprimer le
   biais du survivant, plus fort sur 10 ans.
8. **Cache disque des cotations** : utile pour itérer vite sur le calibrage.
9. **Qualité du dividende, risque de portefeuille** : taux de distribution, limite par
   secteur, trailing stop.
