# gestion-du-risque
- Avant chaque position : perte maximale acceptable, scénario d'invalidation écrit (prix, fait ou date). Pas de scénario d'invalidation = thèse pas prête.
- La taille de position découle de la perte max et de la distance au stop, pas l'inverse.
- Respecte une part maximale par ligne et par secteur. Plusieurs actions dépendant du même facteur (même matière première, même thème, mêmes taux) = UN SEUL pari.
- Garder du cash est une position comme une autre.
- À éviter : vendre puis racheter le même titre sans fait nouveau ; acheter uniquement parce que ça a baissé (« couteau qui tombe ») ou uniquement parce que ça a monté ; changer de raison pour justifier une position perdante — si la raison d'achat n'est plus valable, réévalue.
- Règles appliquées par le code (un ordre qui ne les respecte pas est refusé avec la raison) : part maximale par secteur (le secteur vient de donnees_financieres) ; pas d'achat d'un titre la veille ou le jour de ses résultats (crée plutôt un rappel et décide après la publication) ; FREIN D'URGENCE : si le compte perd trop en un jour ou en une semaine, plus aucun achat n'est possible pendant la séance, seules les ventes et la protection (stops) restent permises.
