# Bot IA trading — une équipe de 6 IA avec les fonctions de celles d'Aywen

Inspiré de la vidéo d'Aywen « J'ai laissé 4 IA investir en bourse » : chaque IA a **les mêmes
fonctions** que les siennes. Elle choisit seule ses **outils** (actualité, screener, données
boursières, navigateur web, réseaux, notes, broker), s'appuie sur des **skills** (un socle
commun et une stratégie), garde ses **notes** comme mémoire, et son contexte est remis à zéro à
chaque séance. Mais au lieu de se faire concurrence avec un budget chacune, les **6 IA
travaillent ensemble sur un seul compte** Alpaca paper (argent virtuel), gratuitement.

## L'équipe

| IA | Clé et modèle | Rôle |
|---|---|---|
| Analyste Qualité | Gemini 1 · Gemini 3.5 Flash | propose des entreprises solides à prix raisonnable (comme « Claude ») |
| Analyste Équilibre | Gemini 2 · Gemini 3.5 Flash | propose des idées pour diversifier (comme « ChatGPT ») |
| Analyste Sentiment | Groq 1 · gpt-oss-120b | propose selon l'humeur des réseaux et l'actualité (comme « Grok ») |
| Analyste Contrarien | Groq 2 · Qwen 3.8 | propose des rebonds, de préférence européens (comme « Mistral ») |
| Critique | Groq 3 · gpt-oss-20b | vérifie chaque proposition avec les outils : ok, réserve ou rejet |
| Gérant | Gemini 3 · Gemini 3.5 Flash | **stratégie Qualité** : décide, passe les ordres, tient le journal de l'équipe |

- Les analystes gardent des stratégies différentes : c'est la leçon d'Aywen (même méthode = mêmes
  décisions). C'est le gérant Qualité qui tranche.
- Si une clé ou un modèle est saturé, le routeur passe au modèle suivant, à la clé de relais, puis
  à l'autre fournisseur, sans perdre le fil de la séance. La clé Gemini 3 sert aussi à l'outil
  « Navigateur web » (recherche Google).

## La journée de bourse

| Heure (Paris) | Séance | Ce qui se passe |
|---|---|---|
| **9 h** | Préparation | Bourse de New York fermée. Les 4 analystes cherchent en parallèle et proposent, le critique contrôle, le gérant décide : ses ordres sont **planifiés**. |
| **15 h 30** | Ouverture | Le programme passe les ordres planifiés **dès l'ouverture de New York**, au prix d'ouverture. Un achat est annulé si l'ouverture s'écarte de plus de 5 % du prix du matin. |
| **≈ 19 h 30** (18 h 30 en hiver) | Suivi | Bourse ouverte : l'équipe fait le point sur les positions et le gérant agit en direct si c'est justifié. |

## Une séance, vue de l'intérieur

1. **Analystes** (en parallèle) : chacun relit ses notes, puis enchaîne les outils qu'il choisit,
   par exemple : portefeuille, screener « baisse_semaine », historique du cours, données
   financières, actualités, sentiment Reddit, lecture d'un skill. Il propose ensuite au plus
   3 ordres avec sa thèse (`proposer_ordre`), que les garde-fous vérifient tout de suite.
2. **Critique** : vérifie les faits douteux avec les outils et donne un verdict sur chaque proposition.
3. **Gérant** : relit le journal de l'équipe, ce qui s'est passé sur le compte, les propositions et
   les avis, vérifie si besoin, puis passe les ordres (`passer_ordre`), met à jour le journal et conclut.

Tout est enregistré : c'est le « cerveau » de chaque IA, visible dans le tableau de bord.

**Garde-fous codés en dur** ([bot/risk.py](bot/risk.py)) : 15 % maximum du compte par titre, 5 %
de liquidités gardées, 10 positions au plus, 5 ordres par séance, stop loss obligatoire entre 1 et
15 %, objectif de gain au moins 1,5 fois le stop, pas d'action sous 5 $, **un stop ne se descend
jamais**, pas de rachat d'un titre vendu il y a moins de 2 jours, pas d'aller-retour dans la
journée. Un ordre refusé est renvoyé à l'IA avec la raison.

## Interface (tableau de bord)

Comme le tableau de bord d'Aywen : dernière décision de l'équipe avec les propositions et les
verdicts du critique, journée de bourse en direct (quelle IA réfléchit, quel outil elle utilise),
courbe du compte, plan d'ouverture, positions, et l'historique des séances avec le « cerveau » de
chacune des 6 IA étape par étape.

```bash
python dashboard.py
```

Elle s'ouvre sur http://127.0.0.1:8000 et reste visible uniquement sur ton ordinateur. Le bouton
« Lancer une simulation » fait travailler l'équipe sans rien envoyer ni enregistrer. Le bouton
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
- [bot/agents.py](bot/agents.py) : l'équipe, le déroulé d'une séance et l'exécution à l'ouverture
- [bot/agent_tools.py](bot/agent_tools.py) : les outils que les IA appellent, selon leur rôle
- [bot/comptes.py](bot/comptes.py) : le registre du compte (lots, stops et objectifs suivis chez Alpaca)
- [bot/llm.py](bot/llm.py) : Gemini et Groq avec appel d'outils, relais entre clés et modèles
- [bot/alpaca.py](bot/alpaca.py) : broker et données de marché gratuites (flux IEX)
- [bot/tools.py](bot/tools.py) et [bot/universe.py](bot/universe.py) : indicateurs, screener, fondamentaux, Reddit
- [bot/risk.py](bot/risk.py) et [bot/executor.py](bot/executor.py) : garde-fous et envoi des ordres
- [skills/](skills/) : socle commun et stratégies (modifie-les pour changer le comportement des IA)
- [tests/test_risk.py](tests/test_risk.py) : tests des garde-fous et du registre du compte

## À lire avant tout

La conclusion d'Aywen : les gains de son expérience relèvent surtout de la **chance**. Les IA ne
vont pas plus vite que le marché, et quelques semaines ne prouvent rien. Le workflow force
`ALPACA_PAPER=true`. Passer en argent réel demande une modification volontaire (`ALPACA_PAPER=false`
et `LIVE_TRADING_CONFIRMATION=JE_COMPRENDS_LES_RISQUES`), et ce n'est pas recommandé.
Ce projet est un outil d'expérimentation, pas un conseil en investissement.
