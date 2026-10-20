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

## 5. La comparaison aux concurrents (comparaison_concurrents)
donnees_financieres compare l'entreprise à 3 ou 4 concurrents : les plus grands de la même industrie, complétés si besoin par ceux du même secteur (champ « lien » : industrie ou secteur ; un concurrent du seul secteur compare moins bien).
- « lecture » résume l'écart : « PER attendu 15 contre 18,1 (médiane de 4 concurrents) ».
- Un PER attendu nettement sous la médiane avec une croissance et des marges comparables : décote à expliquer (occasion ou problème caché).
- Un PER attendu au-dessus de la médiane se justifie seulement par une croissance ou des marges nettement supérieures.

## 6. Ce qu'en pensent les analystes et les dirigeants (outil analystes_et_inities)
- revisions_estimations : combien d'analystes ont RELEVÉ ou ABAISSÉ leur estimation de bénéfice sur 30 jours, et de combien l'estimation moyenne a varié. Des estimations qui montent sont l'un des signaux les plus fiables à quelques mois ; des estimations qui baissent avant des résultats sont un avertissement.
- notes_analystes_30j : notes relevées ou abaissées, objectifs de cours relevés ou abaissés, et les 4 dernières décisions. Une seule note ne veut rien dire ; une série de baisses, si.
- dirigeants_6_mois : leurs ventes sont courantes (rémunération, impôts) et peu parlantes. Leurs ACHATS avec leur propre argent sont un vrai signal de confiance, surtout après une baisse (utile à la stratégie Contrarien).
- vente_a_decouvert : part_du_flottant_vendue_pct. Sous 5 %, normal. Au-delà de 15 %, beaucoup d'investisseurs parient sur la baisse : risque élevé, mais aussi possibilité de hausse brutale si une bonne nouvelle les force à racheter (« short squeeze », utile à la stratégie Sentiment). jours_pour_racheter au-delà de 5 renforce ce risque.

## 7. La date des résultats
prochains_resultats et jours_avant_resultats (calculés par le code). Le code refuse un achat 0 ou 1 jour avant les résultats. Au-delà, lis la fiche resultats-d-entreprise avant d'acheter à moins de 10 jours d'une publication.

## 8. Les signaux d'alerte
- Bénéfice en hausse mais flux de trésorerie libre en baisse : la qualité du bénéfice est douteuse.
- Chiffre d'affaires en baisse depuis plusieurs trimestres, et marges qui se resserrent.
- Dette qui grimpe sans que la croissance suive.
- Valorisation très basse sans raison apparente : le marché sait peut-être quelque chose (cherche l'actualité).
- Données manquantes : écris-le. Une analyse sur des chiffres incomplets doit afficher une confiance plus faible.

## La conclusion à écrire
En deux phrases : « entreprise solide, en croissance, valorisée raisonnablement » (ou le contraire), et le chiffre qui t'inquiète le plus.
