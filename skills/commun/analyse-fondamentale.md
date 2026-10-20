# analyse-fondamentale : lire donnees_financieres

donnees_financieres donne la carte d'identité financière d'une entreprise (source : Yahoo Finance). Les repères ci-dessous valent pour une grande entreprise américaine ; compare toujours au SECTEUR, car une banque, un supermarché et un éditeur de logiciels ne se jugent pas pareil.

## 1. Croissance : l'entreprise grandit-elle ?
- croissance_ca_pct : hausse du chiffre d'affaires sur un an (dernier trimestre). Au-dessus de 10 % : croissance nette. Entre 0 et 5 % : entreprise mûre. Négative : activité en recul, à expliquer.
- croissance_benef_pct : hausse du bénéfice. Plus volatile ; un bénéfice qui monte beaucoup plus vite que le chiffre d'affaires vient souvent de baisses de coûts ou de rachats d'actions, moins durables.

## 2. Rentabilité : gagne-t-elle bien sa vie ?
- marge_op_pct (marge opérationnelle) : au-dessus de 20 %, excellente ; entre 10 et 20 %, correcte ; sous 5 %, fragile. Exceptions : la distribution et l'automobile vivent avec des marges faibles (2 à 8 %), le logiciel et les semi-conducteurs avec des marges fortes (25 % et plus).
- marge_nette_pct : ce qui reste après tout (impôts, intérêts).
- roe_pct (rentabilité des fonds propres) : au-dessus de 15 %, bonne. Attention, un ROE très élevé peut venir d'une dette énorme ou de fonds propres négatifs : vérifie toujours la dette.

## 3. Solidité : peut-elle traverser une crise ?
- dette_sur_fp : la dette divisée par les fonds propres, exprimée en % (100 = autant de dette que de fonds propres). Sous 100 : confortable. Au-dessus de 200 : lourd, sauf pour les banques, les assurances et les services publics, qui vivent naturellement avec beaucoup de dette.
- flux_tresorerie_libre : l'argent réellement encaissé après les investissements. Positif et important : l'entreprise finance seule sa croissance, ses dividendes et ses rachats. Négatif : elle brûle de l'argent, il lui faudra emprunter ou émettre des actions.

## 4. Valorisation : le prix est-il raisonnable ?
- per : le prix divisé par le bénéfice des 12 derniers mois. Le marché américain se paie en moyenne autour de 20 fois.
- per_attendu : le même rapport avec le bénéfice ESTIMÉ de l'année prochaine. S'il est bien plus bas que le per, les analystes attendent une forte hausse des bénéfices (à vérifier, ce sont des estimations).
- Rapport croissance / prix : divise per_attendu par croissance_benef_pct. Autour de 1 ou moins : la croissance n'est pas payée cher. Au-delà de 2,5 : il faut une croissance exceptionnelle et durable pour justifier le prix.
- prix_sur_actif : surtout utile pour les banques et les assurances (entre 1 et 1,5 en temps normal).
- rendement_dividende_pct : au-delà de 6 à 7 %, méfiance. Un rendement très élevé vient souvent d'un cours effondré et annonce une baisse du dividende.
- objectif_analystes et avis_analystes : le consensus des analystes. Un objectif 30 % au-dessus du cours n'est pas une preuve : les analystes suivent souvent le prix avec retard. C'est un élément de contexte, jamais une thèse.

## 5. La date des résultats
prochains_resultats et jours_avant_resultats (calculés par le code). Le code refuse un achat 0 ou 1 jour avant les résultats. Au-delà, lis la fiche resultats-d-entreprise avant d'acheter à moins de 10 jours d'une publication.

## 6. Les signaux d'alerte
- Bénéfice en hausse mais flux de trésorerie libre en baisse : la qualité du bénéfice est douteuse.
- Chiffre d'affaires en baisse depuis plusieurs trimestres, et marges qui se resserrent.
- Dette qui grimpe sans que la croissance suive.
- Valorisation très basse sans raison apparente : le marché sait peut-être quelque chose (cherche l'actualité).
- Données manquantes : écris-le. Une analyse sur des chiffres incomplets doit afficher une confiance plus faible.

## La conclusion à écrire
En deux phrases : « entreprise solide, en croissance, valorisée raisonnablement » (ou le contraire), et le chiffre qui t'inquiète le plus.
