# stop-loss-take-profit : placer le stop et l'objectif

## Le principe
Chaque achat part avec deux ordres posés chez le courtier :
- le STOP LOSS vend automatiquement si le cours descend jusqu'à son niveau ;
- l'OBJECTIF (take profit) vend automatiquement si le cours monte jusqu'au sien.
Tu les donnes en pourcentage du prix d'exécution : stop_loss_pct et take_profit_pct.

## Placer le stop : là où la thèse est fausse
1. Cherche le niveau d'INVALIDATION : sous le plus bas récent (cours_20_derniers_jours), sous la sma50 pour une tendance, sous le plus bas qui a suivi la mauvaise nouvelle pour un rebond.
2. Vérifie qu'il est hors du BRUIT : au moins 1,5 à 2 fois l'ATR sous le prix (atr14 dans historique_prix). Exemple : prix 50 $, atr14 1,50 $ (3 %), donc un stop d'au moins 4,5 à 6 %.
3. Convertis en pourcentage : stop_loss_pct = (prix - niveau du stop) ÷ prix × 100.
4. Contrôle : le code impose entre 1 et 15 %. Si le bon stop est à 20 %, le titre est trop agité pour cette stratégie, ou ce n'est pas le bon moment.
Un stop trop serré se fait toucher par le bruit normal et te fait vendre au pire moment. Un stop trop large fait perdre trop. La taille de la position compense (fiche taille-de-position).

## Placer l'objectif
- Cohérent avec la thèse : sous une résistance évidente (plus_haut_52s), ou au niveau que justifie la valorisation.
- Le code exige un objectif d'au moins 1,5 fois le stop (ratio gain/perte). Vise plutôt 2 à 3 fois : avec un ratio de 2, tu peux te tromper une fois sur deux et rester gagnant.
- Exemple : stop 5 %, objectif 10 % (ratio 2) ; stop 7 %, objectif 15 à 20 %.

## Le stop suiveur automatique (le code s'en charge)
- Quand une position gagne 5 %, le programme remonte son stop au prix d'achat : elle ne peut plus perdre d'argent.
- Quand elle gagne 10 %, le stop suit le cours à 5 % en dessous, et remonte à chaque nouvelle séance si le cours monte.
- Conséquence : tu n'as pas besoin de remonter toi-même le stop au prix d'achat. Concentre-toi sur les cas où la thèse justifie de protéger PLUS tôt (résultats proches, nouvelle inquiétante).

## Modifier un stop (gérant, ajuster_stop)
- RÈGLE ABSOLUE : un stop ne descend JAMAIS. Le code le refuse de toute façon.
- On le remonte pour protéger un gain, avant des résultats ou quand la thèse s'affaiblit sans être cassée. Le nouveau stop doit rester sous le cours actuel.
- Chaque modification se justifie par écrit dans le journal de l'équipe.

## Les limites
Un stop n'est pas une garantie : après une très mauvaise nouvelle pendant la nuit, le cours peut ouvrir bien en dessous et la vente se fait à ce prix. C'est pour cela que la taille de la position compte autant que le stop.
