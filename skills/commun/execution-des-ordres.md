# execution-des-ordres
- Les achats sont envoyés en ordre « bracket » : achat au marché + stop loss + take profit attachés, en nombre entier d'actions.
- Checklist : bon symbole ? marché ouvert ? montant cohérent avec la taille calculée et le cash ? stop ET take profit renseignés ?
- Actions possibles : acheter, vendre (tout), alleger (une partie, en %), ajuster_stop (uniquement vers le haut).
- Un seul ordre par titre et par session. Le code applique les limites de risque et rejette tout ordre non conforme.
