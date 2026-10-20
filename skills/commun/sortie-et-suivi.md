# sortie-et-suivi : quand vendre, alléger ou garder

Acheter est facile ; bien vendre fait la différence. Chaque position se revoit à chaque séance de suivi, et avant chaque publication de résultats.

## La revue d'une position (en 4 questions)
Pour chaque ligne de consulter_portefeuille (prix d'achat, cours, plus-value, stop, objectif, thèse, jours_detenue, distance_stop_pct, distance_objectif_pct, perte_si_stop_usd) :
1. La THÈSE tient-elle encore ? Relis-la : les faits qui la fondaient sont-ils toujours vrais ? Un fait nouveau la contredit-il (actualites) ?
2. Le CATALYSEUR attendu a-t-il eu lieu ? S'il est passé sans effet, la raison d'être de la position a disparu.
3. Y a-t-il un RISQUE proche : des résultats dans quelques jours, une décision attendue ?
4. L'achèterais-tu AUJOURD'HUI, à ce prix ? Si la réponse est non, il faut une bonne raison pour la garder.

## Les raisons de vendre
- La thèse est cassée (fait nouveau, prévisions abaissées, catalyseur raté) : on vend, même en perte. C'est la raison la plus importante.
- Le stop ou l'objectif sont touchés : le courtier vend tout seul.
- Le temps : aucun progrès après le double de l'horizon prévu, alors que le catalyseur est passé. L'argent immobilisé ne travaille pas.
- Une bien meilleure idée a besoin de la place (positions ou liquidités au maximum) : vends la plus faible du portefeuille.
- La position a trop grossi (plus de 15 % du compte après une forte hausse) : allège pour revenir à une taille raisonnable.

## Les raisons de NE PAS vendre
- Le cours baisse un peu mais la thèse tient et le stop n'est pas touché : c'est le bruit normal.
- Une mauvaise nouvelle du marché entier, pas de l'entreprise.
- La peur de perdre un gain : le stop suiveur protège déjà les gains (au prix d'achat dès +5 %, puis à 5 % sous le cours à partir de +10 %).

## Alléger plutôt que tout vendre
Vendre 30 à 50 % (passer_ordre avec action « vendre » et un pourcentage) est utile quand la thèse s'affaiblit sans être cassée, avant des résultats risqués, ou quand une position est devenue trop grosse. La protection (stop et objectif) est remise automatiquement sur ce qui reste.

## L'autopsie d'une position fermée
Quand un stop ou un objectif se déclenche, ou après une vente, prends une minute à la séance suivante :
- La thèse était-elle juste ? Le résultat vient-il de la thèse, du marché ou de la chance ?
- Le stop était-il bien placé ? La taille était-elle adaptée ?
- Si tu en tires une RÈGLE réutilisable, écris-la avec noter_lecon. Exemple : « Ne pas garder une position en perte au-delà de ses résultats sans avoir relu la thèse la veille. »
