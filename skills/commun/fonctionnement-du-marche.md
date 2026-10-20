# fonctionnement-du-marche

## Ce que l'équipe peut acheter
- Des actions cotées aux États-Unis (NYSE, Nasdaq), en dollars, via le courtier Alpaca (compte d'entraînement, argent virtuel).
- Les grandes entreprises européennes sont accessibles par leurs ADR cotés à New York (ASML, SAP, NVO, TTE, SHEL, STLA, NOK, ING…) : même entreprise, prix en dollars, donc soumis aussi au taux de change euro-dollar.
- Pas d'action sous 5 $ (interdit par le code) : ce sont des titres peu liquides et faciles à manipuler.
- Le screener couvre environ 170 grandes valeurs ; « plus_actives », « hausse_jour », « baisse_jour » et « tendances_reddit » regardent le marché entier.

## Les horaires
- Séance de New York : 9 h 30 à 16 h 00 (heure de New York), soit 15 h 30 à 22 h 00 à Paris. Pendant une à trois semaines au printemps et à l'automne, les deux pays ne changent pas d'heure le même jour : l'écart tombe à 5 heures (ouverture à 14 h 30 à Paris).
- Avant et après la séance, les échanges existent mais sont rares : les prix y sont peu fiables.
- Bourse fermée le week-end et lors des jours fériés américains (Thanksgiving, Noël, 4 juillet…).

## Comment s'exécutent nos ordres
- Ordre planifié le matin : exécuté au marché juste après l'ouverture. Le premier prix de la journée peut faire un SAUT (gap) par rapport à la veille : le code annule l'achat si l'écart avec le prix du matin dépasse la limite (5 % par défaut).
- Chaque achat part avec son stop et son objectif posés chez le courtier (ordre « bracket ») : ils restent actifs jour et nuit, sans qu'une IA ait besoin d'intervenir.
- Un stop n'est pas un prix garanti : si le cours ouvre bien en dessous (mauvaise nouvelle pendant la nuit), la vente se fait au prix d'ouverture.

## Ce qui fait bouger un cours
- Les résultats trimestriels et surtout les PRÉVISIONS (guidance) : le plus gros moteur à court terme, quatre fois par an.
- Les nouvelles de l'entreprise : produit, contrat, fusion ou rachat, changement de dirigeant, procès, enquête, rappel de produit.
- La macroéconomie : décisions de la Réserve fédérale (taux), inflation, emploi, croissance. Elles déplacent tout le marché à la fois.
- Les flux : entrée ou sortie d'un indice, rachats d'actions, augmentation de capital, ventes d'initiés, échéances d'options (troisième vendredi du mois).
- Le secteur : un concurrent qui publie de mauvais chiffres entraîne souvent tout son secteur.
- Le sentiment : l'emballement des réseaux, la peur générale.

## Les vérités à garder en tête
- Le prix reflète les bénéfices FUTURS attendus, pas les bénéfices passés. Une bonne nouvelle déjà attendue peut faire baisser un cours ; une moins mauvaise que prévu peut le faire monter.
- Capitalisation = prix × nombre d'actions. Une grande capitalisation bouge moins et s'échange mieux qu'une petite.
- Volatilité : un titre qui varie de 3 % par jour peut perdre 15 % en une semaine sans aucune nouvelle. Taille et stop doivent en tenir compte (fiche taille-de-position).
- Personne n'a un avantage de vitesse ici : ton avantage, c'est la rigueur, la patience et la discipline du risque.
