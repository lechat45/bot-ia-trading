# sentiment-reseaux : Reddit, emballements et manipulations

À savoir d'abord : l'humeur des réseaux sociaux est l'une des méthodes les MOINS prouvées (fiche ce-qui-marche-vraiment). Le célèbre article qui prédisait la bourse avec Twitter n'a jamais été reproduit. Sers-t'en pour repérer un risque (un emballement, une manipulation), jamais comme raison d'acheter.

## Les outils
- sentiment_reseaux(symbole) renvoie :
  - reddit : rang parmi les actions les plus discutées, mentions_24h, mentions_veille, rang_veille, upvotes. « Hors du top 300 » veut dire peu discuté.
  - articles_3_derniers_jours : le nombre d'articles de presse récents sur le titre.
  - messages_reddit : les titres et le début des messages récents (si l'accès Reddit est configuré).
- screener(critere="tendances_reddit") : les actions les plus discutées sur r/wallstreetbets, r/stocks et d'autres forums.
- X (Twitter) n'a pas d'accès gratuit : pour savoir ce qui s'y dit, pose une question précise à recherche_web.

## Lire les chiffres
- L'ÉVOLUTION compte plus que le niveau. Une action toujours très discutée (comme Tesla ou Nvidia) n'apprend rien. Une action dont les mentions passent de 20 à 300 en un jour, si.
- Rapport mentions_24h / mentions_veille : au-delà de 3, il se passe quelque chose. Cherche le FAIT déclencheur (actualites).
- Mentions en hausse ET articles de presse en hausse : l'attention est réelle et large.
- Mentions en hausse SANS article de presse : l'emballement vient seulement des forums. Prudence maximale.
- Vente à découvert (outil analystes_et_inities) : si plus de 15 % des actions disponibles sont vendues à découvert, une bonne nouvelle peut forcer ces vendeurs à racheter en catastrophe (« short squeeze ») et faire bondir le cours. C'est aussi le signe que beaucoup de professionnels parient sur la baisse : le risque est élevé dans les deux sens.

## Ce que le sentiment peut annoncer
- Un sentiment qui monte avec une vraie nouvelle et un volume inhabituel (volume_vs_moy20 > 2) : l'élan peut durer quelques jours ou semaines.
- Un sentiment euphorique après une hausse de 30 % en une semaine : souvent la fin du mouvement, pas le début. Les derniers arrivés achètent le plus haut.
- Un sentiment très négatif sur une entreprise solide : une possible occasion pour l'analyste Contrarien, à condition de prouver que les faits ne justifient pas la panique.

## Les pièges
- Les campagnes coordonnées (« pump and dump ») : beaucoup de messages enthousiastes sur un petit titre, souvent sans source, puis une chute brutale. Signes d'alerte : petite capitalisation, messages répétitifs, promesses de gains énormes, absence de nouvelle officielle.
- Les bots et les comptes créés pour l'occasion.
- Les captures d'écran sans source, les « on m'a dit que ».
- L'échantillon biaisé : Reddit n'est pas le marché. Les gros investisseurs n'y écrivent pas.

## La règle
Le sentiment est un COMPLÉMENT, jamais une preuve. Une proposition fondée sur le sentiment doit aussi citer : le fait qui l'alimente, la tendance du cours (historique_prix), et ce qui pourrait l'arrêter.
