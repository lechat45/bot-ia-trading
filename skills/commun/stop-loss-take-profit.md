# stop-loss-take-profit
- Stop loss : vente auto si le prix descend au niveau fixé. Take profit : vente auto si le prix monte au niveau fixé. Ex : achat 10 $, stop 8 $, TP 14 $ → risque 2 pour gain visé 4 (ratio 1:2).
- Place le stop là où ta thèse est réellement invalidée (sous un support, au-delà de ~1,5-2 ATR), pas à un % arbitraire trop proche, sinon le bruit le déclenche.
- Calcule le ratio gain/perte avant l'achat.
- RÈGLE ABSOLUE : on ne descend JAMAIS un stop. On peut le remonter pour protéger un gain. (Le code refuse de toute façon un stop abaissé.)
- Un stop ne garantit pas le prix en cas de gap. Toute modification de stop/TP se justifie par écrit.
