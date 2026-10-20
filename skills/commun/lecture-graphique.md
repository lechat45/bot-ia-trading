# lecture-graphique : lire historique_prix

historique_prix te donne des indicateurs déjà calculés par le code. Voici comment les lire, dans l'ordre.

## 1. La tendance (le plus important)
Champs : prix, sma20, sma50, sma200 (moyennes des 20, 50 et 200 derniers jours), perf_1m_pct, perf_3m_pct, perf_1an_pct.
- Tendance haussière saine : prix > sma50 > sma200, et perf_3m_pct positive.
- Tendance baissière : prix < sma50 < sma200, et perf_3m_pct négative. Acheter ici, c'est parier contre le courant : il faut une raison forte et datée (stratégie Contrarien).
- Sans direction : les moyennes s'emmêlent, le prix oscille autour. Les signaux y sont peu fiables.
- La sma200 est la ligne que tout le marché regarde : un prix qui la casse à la baisse avec du volume est un avertissement.

## 2. La force relative : mieux ou moins bien que le marché ?
Champ marche_SPY : les performances du S&P 500 sur 5 jours, 1 mois et 3 mois.
- Compare perf_1m_pct et perf_3m_pct du titre à celles du SPY. Un titre qui monte plus que le marché dans une hausse, et baisse moins dans une baisse, est un « leader ».
- Une baisse de 8 % quand le marché a perdu 7 % n'est pas un problème de l'entreprise : c'est le marché.

## 3. L'élan : RSI et distance au plus haut
- rsi14 au-dessus de 70 : la hausse a été très rapide. Dans une tendance haussière, ce n'est PAS un signal de vente à lui seul, mais acheter là, c'est acheter cher : attends un repli ou réduis la taille.
- rsi14 sous 30 : la baisse a été très rapide. Dans une tendance baissière, le RSI peut rester bas longtemps. Ce n'est pas un signal d'achat à lui seul.
- ecart_plus_haut_pct : la distance au plus haut sur un an. Entre 0 et -5 % : le titre est près de ses sommets (élan fort). Sous -30 % : le marché doute sérieusement de l'entreprise, il faut savoir pourquoi.
- plus_haut_52s et plus_bas_52s : les niveaux que les investisseurs ont en tête.

## 4. Le bruit : ATR et volatilité
- atr14 : la variation habituelle d'une journée, en dollars. ATR en % = atr14 / prix × 100.
- volat_annuelle_pct : la volatilité sur un an. Sous 25 % : titre calme. Entre 25 et 45 % : normal pour une valeur de croissance. Au-delà de 45 % : titre très agité, à prendre en petite taille.
- Le stop doit être hors du bruit : au moins 1,5 à 2 ATR sous le prix d'achat. Exemple : prix 200 $, atr14 4 $ (2 %) donne un stop d'au moins 3 à 4 %, soit vers 192-194 $ (fiche stop-loss-take-profit).

## 5. Le volume : le mouvement est-il sérieux ?
- volume_vs_moy20 : le volume du jour divisé par la moyenne des 20 jours. Au-dessus de 2 : volume inhabituel, quelque chose se passe (cherche la nouvelle avec actualites).
- Une hausse avec gros volume est plus crédible qu'une hausse sans volume. Une chute avec gros volume après une mauvaise nouvelle peut marquer une capitulation, ou le début d'une longue baisse : il faut regarder les séances suivantes.

## 6. Les cours bruts
- cours_20_derniers_jours : repère les plus bas récents (supports) et les plus hauts récents (résistances). Un support est un bon endroit pour placer un stop juste en dessous.
- cours_hebdo_1an : la forme générale de l'année, une valeur par semaine.
- date_dernier_cours : vérifie que les données sont à jour.

## Les limites
Un graphique décrit le passé, il ne prédit rien. Il sert à choisir le MOMENT et le NIVEAU (entrée, stop), pas à décider SI une entreprise mérite d'être achetée : ça, c'est le rôle des fondamentaux et des catalyseurs. Avant d'interpréter un mouvement fort, cherche-en toujours la raison.
