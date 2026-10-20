# gestion-du-risque : protéger le compte

Le but n'est pas d'avoir raison à chaque fois, mais de perdre peu quand on a tort et de gagner bien quand on a raison. Une perte de 50 % demande ensuite +100 % pour revenir : éviter les grosses pertes est la première source de performance.

## Avant chaque achat : la liste de contrôle
1. La thèse est complète, avec un point d'invalidation écrit (fiche these-d-investissement).
2. Le stop correspond à ce point et il est hors du bruit (fiche stop-loss-take-profit).
3. La taille découle du risque accepté (fiche taille-de-position) : 1 % du compte au maximum.
4. L'objectif vaut au moins 2 fois le stop.
5. Pas de résultats dans les 10 jours, ou alors en demi-taille et en connaissance de cause.
6. La position ne fait pas doublon avec une position existante (même secteur, même thème).
7. Le contexte de marché ne contredit pas l'idée (fiche contexte-macro).

## Le risque du portefeuille entier
- Diversification : vise au moins 4 secteurs différents dès que l'équipe détient 5 positions ou plus.
- Paris corrélés : deux fabricants de puces, une compagnie pétrolière et un sous-traitant pétrolier, trois valeurs très sensibles aux taux… c'est UN seul pari. Additionne leurs risques.
- Risque total : la somme des pertes possibles si TOUS les stops étaient touchés en même temps (montant × stop de chaque position). Garde-la sous 6 % du compte.
- Les liquidités sont une position : en marché incertain, garder 30 à 50 % de liquidités est un choix défendable.

## Les règles du code (un ordre qui ne les respecte pas est refusé, avec la raison)
- Taille maximale par titre et par secteur, réserve de liquidités, 10 positions au maximum, 5 ordres par séance, un seul ordre par titre et par séance.
- Stop obligatoire entre 1 et 15 %, objectif d'au moins 1,5 fois le stop, pas d'action sous 5 $.
- Pas d'achat 0 ou 1 jour avant les résultats ; pas de rachat d'un titre vendu il y a moins de 2 jours ; pas de vente d'un titre acheté le jour même.
- FREIN D'URGENCE : si le compte perd 3 % en un jour ou 7 % en une semaine, plus aucun achat n'est possible pendant la séance. Seules les ventes et la protection restent permises.

## Quand le compte va mal
- Après une forte baisse, le réflexe à éviter est d'acheter plus pour « se refaire ». Réduis les tailles, relis les thèses une par une, vends celles qui ne tiennent plus.
- Si le frein d'urgence est actif : profite-en pour faire le tri. Une position dont tu n'achèterais pas une action aujourd'hui doit être questionnée.
- Note la leçon (noter_lecon) si une erreur de méthode est en cause.

## Les comportements interdits
- Vendre puis racheter le même titre sans fait nouveau.
- Acheter seulement parce que ça a baissé (« couteau qui tombe ») ou seulement parce que ça a monté.
- Changer de raison pour justifier une position perdante.
- Abaisser un stop (le code le refuse).
