# Bot IA trading — l'expérience d'Aywen avec Gemini et Groq sur Alpaca

Reprise de la vidéo d'Aywen « J'ai laissé 4 IA investir en bourse » : **4 IA autonomes**, chacune
avec **son modèle, sa stratégie et son propre sous-compte**, qui décident seules quels **outils**
utiliser (actualité, screener, données financières, navigateur web, réseaux, notes, broker) en
s'appuyant sur des **skills** (un socle commun et une stratégie par IA). Le tout en **paper
trading** (argent virtuel) sur Alpaca, et gratuitement.

## Les 4 IA

| IA | Modèle (clé) | Stratégie (comme dans la vidéo) | Sous-compte |
|---|---|---|---|
| Analyste Qualité | Gemini 3.5 Flash (clé Gemini 1) | comme « Claude » : chiffres, patience | 25 000 $ |
| Analyste Équilibre | Gemini 3.5 Flash (clé Gemini 2) | comme « ChatGPT » : diversification | 25 000 $ |
| Analyste Sentiment | gpt-oss-120b (clé Groq 1) | comme « Grok » : humeur des réseaux, risque accepté | 25 000 $ |
| Analyste Contrarien | Qwen 3.8 (clé Groq 2) | comme « Mistral » : rebonds, préférence Europe | 25 000 $ |

- **Clé Gemini 3** : fait tourner l'outil « Navigateur web » (recherche Google) pour les 4 IA.
- **Clé Groq 3** : clé de relais. Si une clé ou un modèle est saturé, le routeur passe au modèle
  suivant, à la clé relais, puis à l'autre fournisseur, sans perdre le fil de la séance.
- Les sous-comptes sont tenus par le programme ([bot/comptes.py](bot/comptes.py)) : chaque achat
  est attribué à l'IA qui l'a décidé, avec ses propres stop loss et objectifs chez Alpaca.

## La journée de bourse

| Heure (Paris) | Séance | Ce qui se passe |
|---|---|---|
| **9 h** | Préparation | Bourse de New York fermée. Chaque IA relit ses notes, consulte son sous-compte, utilise ses outils et décide quoi acheter ou vendre. Ses ordres sont **planifiés**. |
| **15 h 30** | Ouverture | Le programme passe les ordres planifiés **dès l'ouverture de New York**, au prix d'ouverture. Un achat est annulé si l'ouverture s'écarte de plus de 5 % du prix du matin. |
| **≈ 19 h 30** (18 h 30 en hiver) | Suivi | Bourse ouverte : chaque IA fait le point (thèse, stop, actualité) et agit en direct si c'est justifié. |

C'est l'équivalent de la note que « Claude » se laisse le matin dans la vidéo pour acheter
Accenture à l'ouverture de New York.

## Une séance, vue de l'intérieur

L'IA reçoit ses notes et ce qui s'est passé sur son sous-compte depuis la dernière séance (ordres
exécutés, stop déclenché…), puis enchaîne les outils qu'elle choisit, par exemple : consulter son
portefeuille, screener « baisse_semaine », historique du cours, données financières, actualités,
sentiment Reddit, lecture du skill « gestion-du-risque », ordre avec sa thèse, réécriture de ses
notes, compte rendu. Tout est enregistré : c'est le « cerveau » visible dans le tableau de bord.

**Garde-fous codés en dur** ([bot/risk.py](bot/risk.py)), appliqués au sous-compte de chaque IA :
25 % maximum par titre, 5 % de liquidités gardées, 8 positions au plus, 5 ordres par séance, stop
loss obligatoire entre 1 et 15 %, objectif de gain au moins 1,5 fois le stop, pas d'action sous
5 $, **un stop ne se descend jamais**, pas de rachat d'un titre vendu il y a moins de 2 jours, pas
d'aller-retour dans la journée. Un ordre refusé est renvoyé à l'IA avec la raison.

## Interface (tableau de bord)

Comme le tableau de bord d'Aywen : classement des 4 IA, journée de bourse en direct (quelle IA
réfléchit, quel outil elle utilise), courbe de chaque sous-compte, plan d'ouverture, positions de
chaque IA, et l'historique des séances avec le « cerveau » de chaque IA étape par étape.

```bash
python dashboard.py
```

Elle s'ouvre sur http://127.0.0.1:8000 et reste visible uniquement sur ton ordinateur. Le bouton
« Lancer une simulation » fait travailler les 4 IA sans rien envoyer ni enregistrer. Le bouton
« Séance réelle » lance une vraie séance sur le compte Alpaca paper, après confirmation. Sans clés dans
`.env`, l'interface démarre en **mode démo** avec de fausses données.

Pour voir les sessions lancées par GitHub Actions, récupère la mémoire avant d'ouvrir l'interface :

```bash
git pull
```

## Mise en route

### 1. Les clés (ne les colle jamais dans un chat ni dans le code)

- **Alpaca** : crée un compte sur https://app.alpaca.markets, passe sur **Paper Trading**, puis
  génère une clé API (Key ID et Secret).
- **Gemini** : https://aistudio.google.com/apikey. Les quotas gratuits sont **par projet Google
  Cloud** : crée chaque clé dans un **projet différent**, sinon les 3 clés partagent le même quota.
- **Groq** : https://console.groq.com/keys. Les quotas sont **par organisation** : 3 clés dans la
  même organisation partagent le même quota. Elles servent quand même à séparer les agents et à
  prendre le relais en cas d'erreur.

> Créer plusieurs comptes uniquement pour multiplier les quotas gratuits peut enfreindre les
> conditions d'utilisation de Google et de Groq. Reste sur tes propres comptes et projets.

### 2. Test en local (Windows)

```bash
pip install -r requirements.txt
```

```bash
copy .env.example .env
```

Vérifie tes clés (elles ne sont jamais affichées) :

```bash
python check_keys.py
```

Puis lance une séance de préparation en simulation (`--force` permet de tourner à n'importe quelle heure) :

```bash
python main.py --mode preparation --dry-run --force
```

Test sans aucune clé, avec de fausses données :

```bash
python main.py --offline
```

Le rapport s'ouvre dans `memoire/sessions/`.

### 3. Hébergement gratuit avec GitHub Actions

1. Crée un dépôt sur GitHub, **public ou privé** (voir le choix plus bas), et pousse ce dossier.
   Le fichier `.env` reste sur ton PC : il est ignoré par git.
2. Dans **Settings → Secrets and variables → Actions → Secrets**, ajoute ces 8 secrets :
   `GEMINI_API_KEY_1`, `GEMINI_API_KEY_2`, `GEMINI_API_KEY_3`, `GROQ_API_KEY_1`, `GROQ_API_KEY_2`,
   `GROQ_API_KEY_3`, `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`.
3. Dans l'onglet **Actions**, ouvre « Bot IA trading », puis **Run workflow** (simulation cochée)
   pour un premier essai.
4. Ensuite, tout tourne seul chaque jour de bourse : préparation à 9 h, exécution à l'ouverture,
   suivi en fin d'après-midi. Dans **Run workflow**, tu peux aussi lancer une séance à la main
   (préparation, suivi ou ouverture), en simulation ou non.

### 4. Le tableau de bord en ligne

Après chaque session, GitHub Actions génère une version en ligne de l'interface
([build_site.py](build_site.py)) et la publie. Cette version est en lecture seule ; le bouton
« Lancer sur GitHub » ouvre la page Actions. Aucune clé n'y figure.

**Choix A : dépôt public + GitHub Pages (le plus simple)**
- Dans **Settings → Pages → Source**, choisis « **GitHub Actions** ». C'est tout.
- Adresse du site : `https://<ton-pseudo>.github.io/<nom-du-depot>/`
- Avantage : minutes GitHub Actions illimitées.
- Inconvénient : tout le monde peut voir le code, les trades, les notes des agents et le site.
  Les clés restent secrètes dans les Secrets.

**Choix B : dépôt privé + Cloudflare Pages (gratuit, code privé)**
GitHub Pages n'est pas disponible sur un dépôt privé avec un compte gratuit ; Cloudflare Pages
l'est.
1. Crée un compte gratuit sur https://dash.cloudflare.com.
2. Note ton **Account ID** (sur la page d'accueil, colonne de droite, ou dans l'adresse
   `dash.cloudflare.com/<account-id>`).
3. **My Profile → API Tokens → Create Token**, modèle « Edit Cloudflare Workers », ou un jeton
   personnalisé avec la permission *Account → Cloudflare Pages → Edit*.
4. Sur GitHub, ajoute les secrets `CLOUDFLARE_API_TOKEN` et `CLOUDFLARE_ACCOUNT_ID`, puis dans
   l'onglet **Variables** une variable `CLOUDFLARE_PROJECT` = `bot-ia-trading` (le nom du site).
5. Adresse du site : `https://bot-ia-trading.pages.dev` (si le nom est déjà pris, choisis-en un autre).
- Avantage : le code et la mémoire restent privés.
- L'adresse du site reste publique pour qui la connaît. Pour la protéger par e-mail, active
  **Cloudflare Access** (gratuit jusqu'à 50 utilisateurs) : Zero Trust → Access → Applications.

Coût : **0 €**. Un dépôt public a des minutes Actions illimitées. Un dépôt privé en a 2 000 par
mois ; l'attente de l'ouverture en hiver (jusqu'à 70 min par jour) peut alors les dépasser.

## Fichiers

- [main.py](main.py) : lance une séance (`--mode preparation | ouverture | suivi`)
- [dashboard.py](dashboard.py) et [dashboard/](dashboard/) : l'interface ; [build_site.py](build_site.py) : sa version en ligne
- [check_keys.py](check_keys.py) : vérifie les clés du `.env` sans les afficher
- [bot/agents.py](bot/agents.py) : les 4 IA, leur séance de travail et l'exécution à l'ouverture
- [bot/agent_tools.py](bot/agent_tools.py) : les outils que les IA appellent
- [bot/comptes.py](bot/comptes.py) : les sous-comptes
- [bot/llm.py](bot/llm.py) : Gemini et Groq avec appel d'outils, relais entre clés et modèles
- [bot/alpaca.py](bot/alpaca.py) : broker et données de marché gratuites (flux IEX)
- [bot/tools.py](bot/tools.py) et [bot/universe.py](bot/universe.py) : indicateurs, screener, fondamentaux, Reddit
- [bot/risk.py](bot/risk.py) et [bot/executor.py](bot/executor.py) : garde-fous et envoi des ordres
- [skills/](skills/) : socle commun et stratégies (modifie-les pour changer le comportement des IA)
- [tests/test_risk.py](tests/test_risk.py) : tests des garde-fous et des sous-comptes

## À lire avant tout

La conclusion d'Aywen : les gains de son expérience relèvent surtout de la **chance**. Les IA ne
vont pas plus vite que le marché, et quelques semaines ne prouvent rien. Le workflow force
`ALPACA_PAPER=true`. Passer en argent réel demande une modification volontaire (`ALPACA_PAPER=false`
et `LIVE_TRADING_CONFIRMATION=JE_COMPRENDS_LES_RISQUES`), et ce n'est pas recommandé.
Ce projet est un outil d'expérimentation, pas un conseil en investissement.
