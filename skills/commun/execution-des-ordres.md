# execution-des-ordres
- Analyste : proposer_ordre(action, symbole, montant_usd ou pourcentage, stop_loss_pct, take_profit_pct, these, confiance). Les garde-fous la vérifient tout de suite ; si elle est refusée, la raison te revient. 3 propositions au maximum par séance.
- Gérant : passer_ordre(action="acheter", symbole, montant_usd, stop_loss_pct, take_profit_pct, these, source) achète un nombre entier d'actions avec un stop loss et un objectif de gain posés automatiquement chez le courtier (ordre « bracket ») ; les pourcentages s'appliquent au prix d'exécution. passer_ordre(action="vendre", symbole, pourcentage, these) vend tout (100) ou une partie ; la protection est remise sur le reste.
- Bourse FERMÉE : l'ordre du gérant est planifié et exécuté à l'ouverture de New York ; il est annulé si le cours d'ouverture s'écarte trop du prix de référence du matin. annuler_ordre retire un ordre planifié.
- Bourse OUVERTE : exécution immédiate ; vérifie le résultat renvoyé (prix, quantité).
- ajuster_stop : uniquement vers le haut, jamais vers le bas.
- Checklist : bon symbole (actions cotées aux États-Unis, y compris les ADR européens) ? montant cohérent avec la perte maximale et les liquidités ? stop au niveau d'invalidation réel ? ratio gain/perte suffisant ?
- Un seul ordre par titre et par séance.
