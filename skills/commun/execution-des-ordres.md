# execution-des-ordres : proposer, décider, exécuter

## Analyste : proposer_ordre
proposer_ordre(action, symbole, montant_usd, stop_loss_pct, take_profit_pct, these, confiance)
- action : « acheter » ou « vendre » (pour vendre une position du compte, donne pourcentage au lieu de montant_usd : 100 = tout, 50 = la moitié).
- confiance : « faible », « moyen » ou « eleve ».
- MONTANT FACULTATIF : sans montant_usd, le code calcule le montant d'un achat selon ta confiance et ton stop (fiche taille-de-position) et le ramène aux limites. La réponse indique toujours risque_pct_du_compte (la perte si le stop est touché, en % du compte) et ratio_gain_perte.
- 3 propositions au maximum par séance, un seul titre par proposition. Les garde-fous vérifient tout de suite : un montant trop élevé est ramené à la limite, une règle non respectée te revient avec sa raison.
- Tu reçois un identifiant (ex. « qualite-1 ») : le critique donnera son avis dessus, puis le gérant décidera.

## Gérant : passer_ordre
- Achat : passer_ordre(action="acheter", symbole, montant_usd, stop_loss_pct, take_profit_pct, these, source, confiance). Comme pour une proposition, montant_usd peut être omis : il est alors calculé selon la confiance et le stop. Indique dans source l'identifiant de la proposition retenue (ex. « qualite-1 »), ou rien si l'idée est la tienne.
- Vente : passer_ordre(action="vendre", symbole, pourcentage, these). La protection est remise automatiquement sur ce qui reste.
- Le nombre d'actions est entier : le montant est arrondi à l'action inférieure. Les pourcentages de stop et d'objectif s'appliquent au PRIX D'EXÉCUTION.
- 5 ordres au maximum par séance, un seul par titre.

## Bourse fermée ou ouverte
- FERMÉE (séance de préparation) : l'ordre est PLANIFIÉ et exécuté juste après l'ouverture. Il est annulé si le premier cours s'écarte de plus de 5 % du prix de référence du matin, et réduit si les limites ont changé entre-temps. annuler_ordre(symbole) retire un ordre planifié.
- OUVERTE (séance de suivi) : exécution immédiate. Lis le résultat renvoyé (quantité, prix, stop, objectif) et note-le dans le journal.

## Remonter un stop : ajuster_stop
ajuster_stop(symbole, nouveau_stop) avec un PRIX en dollars (pas un pourcentage), plus haut que le stop actuel et plus bas que le cours. Le stop suiveur automatique le fait déjà à partir de +5 % de gain (fiche stop-loss-take-profit).

## Les refus fréquents et comment les corriger
- « montant trop élevé : maximum X $ » : propose au plus X $, ou libère de la place.
- « ratio gain/perte … » : l'objectif doit valoir au moins 1,5 fois le stop. Monte l'objectif si la thèse le justifie, sinon renonce.
- « stop_loss_pct doit être entre 1 et 15 » : revois le niveau d'invalidation (fiche stop-loss-take-profit).
- « publie ses résultats dans 0 ou 1 jour » : crée un rappel pour décider après la publication.
- « vendu il y a moins de 2 jours » : pas d'aller-retour, attends un fait nouveau.
- « acheté aujourd'hui » : impossible de revendre le jour même.
- « déjà 10 positions » : vends d'abord la plus faible si l'idée le mérite vraiment.
- « frein d'urgence actif » : aucun achat pendant la séance ; concentre-toi sur la protection.
- « limite de 35 % par secteur » : le secteur est déjà trop représenté ; choisis une idée d'un autre secteur.

## Avant d'envoyer : la dernière vérification
Bon symbole ? Montant calculé (fiche taille-de-position) et dans les limites ? Stop au niveau d'invalidation ? Objectif au moins 2 fois le stop ? Pas de résultats imminents ? Thèse complète ?
