# actualite-et-catalyseurs

Un catalyseur est un événement qui peut faire bouger un cours : résultats, journée investisseurs, lancement de produit, décision d'une autorité, procès, fusion, entrée dans un indice, décision de la Fed. Une thèse sans catalyseur peut être juste mais mettre très longtemps à payer.

## 1. Juger une information
Pour chaque information, réponds à quatre questions :
1. Qui le dit ? Hiérarchie des sources : l'entreprise elle-même (communiqué, relations investisseurs) et les autorités (SEC, FDA, banques centrales) > les grandes agences et la presse financière (Reuters, Bloomberg, Wall Street Journal, CNBC, Financial Times) > les sites spécialisés > les blogs, forums et réseaux.
2. Quand ? Une info d'il y a trois jours est déjà dans le prix.
3. Est-ce un fait, une rumeur ou une opinion ? « Selon des sources proches du dossier » est une rumeur. Une note d'analyste est une opinion.
4. Est-elle confirmée par une deuxième source indépendante ?

## 2. Est-ce déjà dans le prix ?
Regarde la réaction du cours depuis la publication (historique_prix : perf_1j_pct, perf_5j_pct, volume_vs_moy20).
- Le cours a déjà bondi de 15 % : l'essentiel est fait. Une thèse doit expliquer pourquoi la hausse continuerait.
- Le cours n'a pas réagi à une nouvelle importante : soit le marché ne la juge pas importante, soit il ne l'a pas encore comprise. Le second cas est rare : sois honnête.

## 3. Dater chaque catalyseur
- Donne une date exacte et le nombre de jours jusqu'à elle. Pour les résultats, utilise jours_avant_resultats (calculé par le code).
- Un catalyseur situé APRÈS l'horizon de ta position ne justifie pas l'achat. Exemple : un horizon d'un mois et un produit lancé dans six mois.
- Date introuvable après une recherche : écris « inconnue » et avance. Ne cherche pas la même date plusieurs fois (fiche biais-et-erreurs).

## 4. Utiliser les bons outils
- actualites(symbole) : le fil financier en direct sur une action (Alpaca), complété par les articles de la grande presse trouvés par Google Actualités (repérés par « Google Actualités » dans la source). C'est le premier réflexe, gratuit en quotas.
- actualites() sans symbole : les dernières nouvelles du marché (le résumé du marché t'en donne déjà les grands titres).
- recherche_web : une question précise, quand le fil ne suffit pas (fiche recherche-web).
- lire_page : ouvrir la source d'origine (communiqué, article) avant de te fier à un titre.

## 5. Les rappels : ne rien oublier
- Un événement daté qui pourrait justifier une décision plus tard : creer_rappel(date, titre, details, symbole, seance). Dans details, écris ce qu'il faudra vérifier et la décision à prendre selon le résultat.
- Le jour venu, le rappel est présenté à toute l'équipe. Une fois traité, même par « ne rien faire », marque-le avec terminer_rappel(id, note) en écrivant ce qui a été décidé.
- Les dates de résultats des actions détenues sont ajoutées automatiquement.
- 30 rappels actifs au maximum : n'en crée que pour des événements qui comptent vraiment.
