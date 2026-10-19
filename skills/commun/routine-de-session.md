# routine-de-session
Deux séances par jour de bourse, comme chez Aywen :
- PRÉPARATION (le matin, bourse de New York fermée) : tu décides quoi acheter ou vendre. Tes ordres sont planifiés et exécutés automatiquement à l'ouverture (15h30 heure de Paris).
- SUIVI (bourse ouverte) : tu fais le point sur tes positions (thèse, stop, catalyseurs) et tu agis en direct si c'est justifié.

Étapes :
1. Lire les notes et les événements fournis au début de la séance (ordres exécutés, stops déclenchés).
2. consulter_portefeuille : valeur, positions, ordres planifiés, liquidités, limites.
3. Vérifier chaque position : la thèse tient-elle ? fait nouveau ? catalyseur proche ?
4. Chercher des opportunités si pertinent : screener, historique_prix, donnees_financieres, actualites, sentiment_reseaux (recherche_web pour une question précise).
5. Rédiger la thèse de toute décision, puis passer_ordre.
6. ecrire_notes : réécrire tes notes (elles remplacent les précédentes).
7. terminer_session avec ton compte rendu.

Format de thèse (paramètre « these ») : décision et montant ; arguments (faits datés et sourcés) ; risques ; invalidation (prix ou fait) ; sortie (stop, objectif, horizon) ; confiance (faible, moyen, élevé) et pourquoi.

Efficacité : peu d'idées analysées en profondeur plutôt que beaucoup survolées. Info introuvable : note-la « inconnue » et avance. Tes appels d'outils sont limités par séance.
