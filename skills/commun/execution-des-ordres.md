# execution-des-ordres
- passer_ordre(action="acheter", symbole, montant_usd, stop_loss_pct, take_profit_pct, these) : achat d'un nombre entier d'actions avec un stop loss et un objectif de gain posés automatiquement chez le courtier (ordre « bracket »). Les pourcentages s'appliquent au prix d'exécution.
- passer_ordre(action="vendre", symbole, pourcentage, these) : vend tout (100) ou une partie de la position ; la protection est remise sur le reste.
- Bourse FERMÉE : l'ordre est planifié et exécuté à l'ouverture de New York. Il est annulé si le cours d'ouverture s'écarte trop du prix de référence du matin. annuler_ordre retire un ordre planifié.
- Bourse OUVERTE : exécution immédiate ; vérifie le résultat renvoyé (prix, quantité).
- ajuster_stop : uniquement vers le haut, jamais vers le bas.
- Checklist avant d'envoyer : bon symbole (actions cotées aux États-Unis, y compris les ADR européens) ? montant cohérent avec ta perte maximale et tes liquidités ? stop au niveau d'invalidation réel ? ratio gain/perte suffisant ?
- Un ordre refusé par le code revient avec la raison : corrige-le si ta thèse tient toujours, sinon renonce.
- Un seul ordre par titre et par séance.
