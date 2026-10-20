# taille-de-position : combien acheter ?

La taille d'une position se CALCULE à partir du risque accepté et de la distance au stop. Elle ne se choisit jamais au feeling ni en fonction de l'envie de gagner.

## La formule
montant = (valeur du compte × risque accepté) ÷ distance au stop
- La valeur du compte et les liquidités sont dans consulter_portefeuille.
- Le risque accepté, c'est la part du compte que tu acceptes de perdre si le stop est touché :
  - confiance faible : 0,25 à 0,5 % du compte ;
  - confiance moyenne : 0,5 à 0,75 % ;
  - confiance élevée : 0,75 à 1 %. Jamais plus de 1 % sur une seule idée.
- La distance au stop est le stop_loss_pct de l'ordre.

## Le code peut le calculer pour toi
Si tu ne donnes pas de montant_usd à proposer_ordre ou passer_ordre, le code applique cette formule avec : confiance faible 0,4 %, moyenne 0,6 %, élevée 0,9 % du compte. Le résultat est ramené aux limites, et la réponse indique le risque réellement pris (risque_pct_du_compte). C'est la façon la plus sûre d'éviter une erreur de calcul.

## Exemples avec un compte de 100 000 $
- Confiance moyenne (0,5 %), stop à 5 % : 100 000 × 0,005 ÷ 0,05 = 10 000 $.
- Confiance élevée (1 %), stop à 8 % : 100 000 × 0,01 ÷ 0,08 = 12 500 $.
- Confiance élevée (1 %), stop à 5 % : le calcul donne 20 000 $, mais la limite du code par titre (15 % du compte par défaut, soit 15 000 $) s'applique : 15 000 $.
- Confiance faible (0,25 %), stop à 10 % (titre agité) : 2 500 $.
Un titre agité demande un stop plus large, donc une position plus petite : c'est normal et sain.

## Les limites du code (un dépassement est refusé ou réduit)
- Taille maximale par titre (15 % du compte par défaut), position déjà détenue comprise.
- 35 % du compte au maximum dans un même secteur, ordres planifiés compris.
- Une réserve de liquidités est toujours gardée (5 % par défaut). Les achats déjà planifiés pour l'ouverture sont déduits des liquidités disponibles.
- 10 positions au maximum.
consulter_portefeuille te donne directement « max_par_titre_usd » et « liquidites_utilisables_usd » : vérifie-les avant de proposer un montant.

## Ajuster selon le contexte
- Marché en « risk-off » ou en correction (fiche contexte-macro) : divise le risque par deux.
- Résultats dans moins de 10 jours : demi-taille au plus.
- Deux idées qui dépendent du même facteur (même secteur, même thème, même matière première) : c'est un seul pari ; leur risque total ne doit pas dépasser celui d'une seule position.
- Après plusieurs pertes d'affilée : réduis la taille le temps de comprendre ce qui ne va pas, n'augmente jamais pour « se refaire ».

## Écrire le calcul dans la thèse
« 10 000 $ = risque 0,5 % (confiance moyenne) avec un stop à 5 %. » Le critique et le gérant doivent pouvoir le vérifier en une seconde.
