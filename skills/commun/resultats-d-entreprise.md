# resultats-d-entreprise : avant et après une publication

Quatre fois par an, chaque entreprise publie ses résultats trimestriels. C'est le moment où un cours peut bondir ou chuter de 10 % ou plus en une nuit. La date est dans donnees_financieres (prochains_resultats, jours_avant_resultats) ; pour les actions détenues, un rappel est créé automatiquement.

## Ce que le marché regarde vraiment
1. Les PRÉVISIONS (guidance) pour les trimestres suivants : de loin le plus important. De bons chiffres avec des prévisions décevantes font chuter le cours.
2. Le chiffre d'affaires et le bénéfice par action, comparés à ce que les analystes ATTENDAIENT (pas au trimestre précédent).
3. Les marges, et les indicateurs propres au secteur (abonnés, commandes, volumes, croissance du cloud…).
4. Le ton de la direction lors de la conférence avec les analystes.

## Avant la publication
- Le code interdit d'acheter 0 ou 1 jour avant les résultats.
- Entre 2 et 10 jours avant : n'ouvre une position que si les résultats SONT la thèse, et alors en demi-taille, en sachant que tu joues à pile ou face sur la réaction.
- Sinon, le meilleur choix est souvent d'attendre : crée un rappel (creer_rappel) pour le lendemain de la publication, avec ce qu'il faudra vérifier.
- Pour une position DÉTENUE, décide AVANT la publication, à la séance de préparation qui précède :
  - garder si la thèse est solide, la position modeste et déjà en gain (le stop est loin) ;
  - alléger (vendre 30 à 50 %) si la position est grosse, en perte, ou si un mauvais chiffre casserait la thèse ;
  - vendre si tu ne détiendrais pas ce titre aujourd'hui sans savoir que tu l'as.

## Après la publication
- Lis les faits : actualites sur le symbole, puis lire_page sur le communiqué de l'entreprise si besoin (page « investor relations »).
- Regarde la RÉACTION du cours : historique_prix (perf_1j_pct, volume_vs_moy20).
  - Hausse forte avec gros volume et prévisions relevées : les bonnes surprises ont souvent une suite pendant plusieurs semaines. Un achat est envisageable dans la ou les deux séances suivantes, stop sous le plus bas du jour de la publication.
  - Chute forte avec prévisions abaissées : ne rachète pas dans la chute. Les révisions à la baisse s'enchaînent souvent. Attends au moins quelques séances de stabilisation.
  - Réaction contraire au chiffre (bons chiffres et cours en baisse) : le marché attendait mieux, ou les prévisions déçoivent. Comprends pourquoi avant d'agir.
- Pour une position détenue : si la publication contredit la thèse, vends ; ne réinvente pas une nouvelle raison de garder (fiche biais-et-erreurs).

## La saison des résultats
Les grandes entreprises publient surtout sur quatre périodes : mi-janvier à mi-février, mi-avril à mi-mai, mi-juillet à mi-août, mi-octobre à mi-novembre. Les résultats d'un leader (banques en premier, puis technologie) donnent le ton à tout son secteur : un concurrent qui publie peut faire bouger ta position.

## Le rappel type
creer_rappel(date = lendemain de la publication, titre = « Résultats de XXX », symbole = « XXX », details = « Vérifier les prévisions et la réaction du cours. Garder si [condition], vendre si [condition]. »)
