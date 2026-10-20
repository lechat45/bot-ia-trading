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
- **Roue de secours Gemma 4** : quand le quota du jour de Gemini est épuisé, les IA Gemini passent à
  Gemma 4, des IA de Google qui marchent avec les mêmes clés et ont un quota gratuit bien plus large
  (environ 1 500 requêtes par jour et par projet). Les IA Groq, quand Groq est saturé, passent elles
  aussi par Gemma avant Gemini, pour laisser le quota Gemini aux IA Gemini. Tes vraies limites sont
  visibles sur https://aistudio.google.com/rate-limit.

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

Au début de chaque séance, le programme prépare un **résumé du marché** donné aux 6 IA : indices,
taux, or, pétrole et dollar, secteurs les plus forts et les plus faibles, positions du compte et
grands titres (la une Économie de Google Actualités et le fil d'Alpaca). Les IA démarrent informées,
sans dépenser d'appels d'outils.

**Séance de suivi allégée** : le soir, si rien de notable ne s'est passé depuis le matin (pas de
rappel du jour, pas de stop ni d'objectif déclenché, S&P 500 et positions calmes), seul le gérant
vérifie les positions. Les analystes et le critique ne sont réveillés que si un événement le justifie,
ce qui économise les quotas gratuits des IA. Une séance lancée à la main reste complète
(`SUIVI_COMPLET=true` pour toujours faire travailler toute l'équipe).

Tout est enregistré : c'est le « cerveau » de chaque IA, visible dans le tableau de bord.

**Garde-fous codés en dur** ([bot/risk.py](bot/risk.py)) : 15 % maximum du compte par titre, 5 %
de liquidités gardées, 10 positions au plus, 5 ordres par séance, stop loss obligatoire entre 1 et
15 %, objectif de gain au moins 1,5 fois le stop, pas d'action sous 5 $, **un stop ne se descend
jamais**, pas de rachat d'un titre vendu il y a moins de 2 jours, pas d'aller-retour dans la
journée, **35 % maximum du compte dans un même secteur**, **pas d'achat la veille ou le jour des
résultats** d'une entreprise. Un ordre refusé est renvoyé à l'IA avec la raison.

**Stop suiveur automatique** : quand une position gagne 5 %, son stop remonte à son prix d'achat
(elle ne peut plus perdre d'argent, et tu reçois une notification) ; à +10 %, il suit le cours à 5 %
en dessous. C'est une règle du code, appliquée à chaque séance quand la bourse est ouverte, sans
attendre une décision d'IA. Réglages : `STOP_SUIVEUR_PCT` (0 pour le désactiver) et
`STOP_SUIVEUR_DISTANCE_PCT`.

**Frein d'urgence** : si le compte perd 3 % en un jour ou 7 % en une semaine, plus aucun achat
n'est possible pendant la séance. Les ventes et les stops restent permis, et tu reçois une
notification. **Contrôle du registre** : à chaque séance, le registre du programme est comparé aux
positions réelles chez Alpaca (un achat fait à la main sur le compte, par exemple) ; un écart
s'affiche sur l'Accueil. Les seuils se règlent dans `.env` (`MAX_SECTOR_PCT`, `FREIN_JOUR_PCT`,
`FREIN_SEMAINE_PCT`).

## Interface (tableau de bord)

4 pages, comme le tableau de bord d'Aywen :
- **Accueil** : valeur du compte, courbe comparée au S&P 500, journée de bourse en direct,
  positions, plan d'ouverture, statistiques (plus forte baisse, ventes gagnantes, gain et perte
  moyens, écart avec le S&P 500), leçons de l'équipe, rappels, bilan de la semaine et état du système.
- **Les IA** : les 6 IA, avec à côté le résumé de leur réflexion et leurs actions, et le
  **classement des analystes** : ce qu'aurait rapporté chacune de leurs idées depuis qu'elle a été
  proposée, achetée ou non, et la part des avis du critique confirmés par la suite.
- **Journal** : chaque outil utilisé et chaque réflexion, filtrés par IA et par type.
- **Bureau** façon Windows : des fenêtres Notes, Recherches web (et pages lues), Actualités,
  Bourse, Screener, Reddit, Ordres (avec plus-values réalisées et stops déclenchés) et Rappels.

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

Vérifie toute l'installation : clés, compte Alpaca, cours, actualités, Reddit, recherche web,
navigateur, appel d'outils de chacune des 6 IA et garde-fous. Les clés ne sont jamais affichées.

```bash
python main.py --verifier
```

Cette vérification se lance aussi **toute seule avant la première séance**, et à chaque séance
tant qu'elle n'a pas réussi. Si un élément critique ne marche pas, la séance est annulée. Le
résultat est enregistré dans `memoire/installation.json` et s'affiche sur l'Accueil.

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
   suivi en fin d'après-midi. Des déclenchements de secours rattrapent un horaire oublié par
   GitHub, sans jamais faire deux fois la même séance. Dans **Run workflow**, tu peux aussi lancer
   une séance à la main (préparation, suivi, ouverture ou vérification), en simulation ou non.
5. Facultatif, dans les mêmes Secrets :
   - `NTFY_TOPIC` : **notifications sur ton téléphone** à chaque plan du jour, achat, vente, stop
     déclenché et bilan. Installe l'application gratuite **ntfy**, abonne-toi à un nom de sujet
     difficile à deviner (par exemple `bot-ia-trading-7f3k9q`) et mets ce nom dans le secret.
   - `REDDIT_CLIENT_ID` et `REDDIT_CLIENT_SECRET` : les IA **lisent les messages Reddit** (titres et
     début des messages), pas seulement le nombre de mentions. Crée une application gratuite de type
     « script » sur https://www.reddit.com/prefs/apps (2 minutes).
   - `TAVILY_API_KEY` : une **recherche web complète de secours** (réponse rédigée et liens) quand le
     quota de Gemini est épuisé. 1 000 recherches gratuites par mois, sans carte bancaire, sur
     https://tavily.com. Sans elle, le secours passe par Google Actualités et Wikipédia.
   - `MISTRAL_API_KEY` : un **3e fournisseur d'IA gratuit**. Avec cette clé, le Contrarien et le critique
     travaillent avec Mistral, ce qui décharge Groq (ses 3 clés partagent un seul quota). Formule gratuite
     « Experiment » sur https://console.mistral.ai, avec vérification par téléphone ; Mistral peut
     utiliser les requêtes gratuites pour entraîner ses modèles (ici : des analyses de marché, sans donnée
     personnelle). Sans clé, rien ne change.
6. Facultatif : **un déclencheur à l'heure exacte**. GitHub retarde parfois ses horaires, ou en oublie
   un quand il est surchargé. Le service gratuit https://cron-job.org peut lancer les séances à la
   minute près, en plus des horaires de GitHub (une séance déjà faite n'est jamais refaite) :
   1. Crée un jeton GitHub à accès précis (**Settings → Developer settings → Fine-grained tokens**),
      limité à ce dépôt, avec la permission **Actions : Read and write**. C'est le même type de jeton
      que celui du bouton « Forcer le lancement ».
   2. Sur cron-job.org, crée 3 tâches, fuseau **Europe/Paris** : 9 h 02 (`preparation`), 14 h 25
      (`ouverture` : la séance attend l'ouverture de New York) et 19 h 00 (`suivi`). « Tous les jours »
      convient : les week-ends et jours fériés, le programme s'arrête seul. Pour chacune :
      - adresse : `https://api.github.com/repos/<ton-pseudo>/<nom-du-depot>/actions/workflows/trading.yml/dispatches`
      - méthode **POST**, en-têtes `Authorization: Bearer <ton jeton>` et `Accept: application/vnd.github+json`
      - corps : `{"ref":"main","inputs":{"mode":"preparation","dry_run":"false","force":"false"}}`
        (remplace `preparation` par `ouverture` ou `suivi`).
   3. `"force":"false"` est indispensable : la séance respecte alors les horaires et ne refait jamais
      une séance déjà faite. Une réponse **204** veut dire que la séance est lancée.
   4. Facultatif, une 4e tâche pour la **veille** : toutes les 30 minutes de 15 h 30 à 21 h 30, avec
      `"mode":"veille"` dans le corps. Sans IA, le code vérifie le compte (positions en forte baisse, stop
      presque touché, nouvelle importante, S&P 500 en chute, stop ou objectif déclenché, frein d'urgence)
      et ne réveille le gérant qu'en cas d'événement nouveau, 3 fois par jour au plus, avec une
      notification. Une veille sans événement ne laisse aucune trace (ni séance, ni site republié).
7. À chaque envoi de code sur GitHub, le workflow **Tests** vérifie tout le programme sans clé
   (garde-fous, mémoire, séances complètes avec de fausses IA, site). Un code cassé est repéré
   avant la séance suivante.

### Ce que les IA peuvent faire en plus

- **Rappels** : une IA note un événement daté (résultats, annonce, décision de la Fed) avec ce qu'il
  faudra vérifier et faire. Le jour venu, il est présenté à toute l'équipe, qui agit en fonction.
  Les dates de résultats des actions détenues sont ajoutées automatiquement.
- **Navigateur** : en plus de la recherche Google, une IA peut ouvrir et lire une page précise
  (article, communiqué, page investisseurs). Les adresses internes sont refusées, et le contenu
  externe est toujours traité comme une donnée à vérifier, jamais comme une instruction.
- **Bilan de la semaine** : chaque vendredi soir, le gérant écrit ce qui a marché, ce qui a raté et
  les leçons. Le bilan s'affiche sur l'Accueil.
- **Mémoire longue** : les notes d'une IA sont limitées à 3 500 caractères. Les vraies leçons
  (une erreur à ne pas refaire, une méthode qui marche) vont dans `memoire/lecons.json` avec l'outil
  `noter_lecon` et depuis le bilan du vendredi. Les 6 IA les relisent à chaque séance.
- **Recherche web économe, avec secours** : une question déjà posée par l'équipe pendant la séance
  ne consomme pas de quota, et les recherches tournent sur les 3 clés Gemini. Quand le quota gratuit
  de Gemini est épuisé, la recherche passe tout de suite à **Tavily** (si tu as mis sa clé), sinon à
  **Google Actualités et Wikipédia**, sans aucune clé : l'IA reçoit alors les titres, sources et dates
  des articles au lieu d'une réponse rédigée.
- **Quotas gardés en mémoire** : un modèle d'IA saturé (quota du jour épuisé, limite de débit) est noté
  dans `memoire/quotas.json` et sauté d'emblée aux séances suivantes, au lieu d'être réessayé pour rien. Si
  la moitié des IA démarrent saturées, la séance réduit d'un tiers leurs appels d'outils. La consommation
  de chaque clé s'affiche dans « État du système ».
- **Achats après l'ouverture** : les ordres planifiés partent 10 minutes après l'ouverture de New York
  (`OUVERTURE_DELAI_MIN`), le temps que les premiers prix, très agités, se calment.
- **Ce que valent les critères du screener** : une fois par semaine, chaque critère est rejoué sur 3 ans de
  cours des grandes valeurs (les 10 actions signalées chaque semaine, et ce qu'elles ont rapporté 5, 20 et
  60 séances plus tard, comparé au S&P 500). Les IA reçoivent ces chiffres au début de chaque séance, et
  le site les affiche sur la page « Les IA » (`memoire/backtest.json`). Un passé ne prédit pas l'avenir.
- **Portefeuilles fantômes** : chaque analyste a 100 000 $ virtuels qui suivent toutes ses idées,
  achetées ou non par le gérant, avec leurs stops et objectifs. C'est la compétition des IA d'Aywen, sans
  risquer le vrai compte ; le résultat s'affiche sur la page « Les IA » et chaque analyste le reçoit.
- **Archivage** : les 60 dernières séances restent lisibles dans `memoire/sessions/`, les plus
  anciennes sont compressées par mois dans `memoire/archives/`.

Deux idées sont volontairement laissées de côté. Les **ordres à cours limité à l'ouverture** : un
ordre limité peut ne jamais être exécuté, et le programme annule déjà un achat si l'ouverture
s'écarte de plus de 5 % du prix du matin. Le **calendrier économique** (Fed, inflation, emploi) :
aucune source gratuite et fiable ne fonctionne sans inscription ; les IA trouvent ces dates avec la
recherche web et en font des rappels.

### 4. Le tableau de bord en ligne

Après chaque session, GitHub Actions génère une version en ligne de l'interface
([build_site.py](build_site.py)) et la publie. Cette version est en lecture seule ; le bouton
« Lancer sur GitHub » ouvre la page Actions. Aucune clé n'y figure.

**Choix A : dépôt public + GitHub Pages (le plus simple)**
- Les workflows rangent le site tout prêt dans la branche **`gh-pages`** (créée au premier
  passage). Dans **Settings → Pages → Build and deployment**, garde la source
  « **Deploy from a branch** », puis choisis la branche **`gh-pages`** et le dossier **`/ (root)`**.
- Le site est republié après chaque séance des IA, et dès qu'une modification de l'interface
  arrive sur `main` (workflow « Publier le site », qui ne lance pas les IA).
- Adresse du site : `https://<ton-pseudo>.github.io/<nom-du-depot>/`
- Si une séance n'a pas eu lieu (GitHub saute parfois ses horaires), le site affiche une bannière
  « Séance manquée », calculée par ton navigateur, même si plus rien ne tourne. Avec `NTFY_TOPIC`,
  la séance suivante te prévient aussi sur ton téléphone (une seule fois par jour).
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
- [check_keys.py](check_keys.py) : vérifie les clés du `.env` sans les afficher ; [bot/verification.py](bot/verification.py) : la vérification complète (`python main.py --verifier`)
- [bot/notify.py](bot/notify.py) : notifications sur le téléphone (ntfy)
- [bot/agents.py](bot/agents.py) : l'équipe, le déroulé d'une séance et l'exécution à l'ouverture
- [bot/agent_tools.py](bot/agent_tools.py) : les outils que les IA appellent, selon leur rôle
- [bot/comptes.py](bot/comptes.py) : le registre du compte (lots, stops et objectifs suivis chez Alpaca)
- [bot/llm.py](bot/llm.py) : Gemini et Groq avec appel d'outils, relais entre clés et modèles
- [bot/alpaca.py](bot/alpaca.py) : broker et données de marché gratuites (flux IEX)
- [bot/tools.py](bot/tools.py) et [bot/universe.py](bot/universe.py) : indicateurs, screener, fondamentaux, Reddit
- [bot/risk.py](bot/risk.py) et [bot/executor.py](bot/executor.py) : garde-fous et envoi des ordres
- [skills/](skills/) : le savoir-faire des IA (modifie-les pour changer leur comportement) :
  - lu à chaque séance : la charte de l'équipe (`commun/00-lisez-moi.md`), la routine
    (`commun/routine-de-session.md`) et la stratégie de chaque IA (`strategies/`), avec des critères
    chiffrés, les screeners à utiliser, et le stop, la taille et l'horizon propres à chaque style ;
  - lu à la demande (outil `lire_skill`) : 16 fiches détaillées, dont la lecture du résumé du marché,
    des graphiques et des données financières, les résultats d'entreprise, la thèse
    d'investissement, le calcul de la taille de position, le stop suiveur, la sortie d'une position
    et les biais de raisonnement ;
  - [tests/test_skills.py](tests/test_skills.py) vérifie les renvois entre fiches, les outils cités,
    et que les consignes restent sous 10 000 caractères (les quotas gratuits en dépendent).
- [tests/test_risk.py](tests/test_risk.py) : tests des garde-fous et du registre du compte ;
  [tests/test_memoire.py](tests/test_memoire.py) : tests des leçons et de l'archivage ;
  [.github/workflows/tests.yml](.github/workflows/tests.yml) : les lance à chaque envoi
- `memoire/` : notes, plan, rappels, leçons, propositions des analystes (pour le classement),
  journal des ordres, séances et bilans, recommités après chaque séance

## À lire avant tout

La conclusion d'Aywen : les gains de son expérience relèvent surtout de la **chance**. Les IA ne
vont pas plus vite que le marché, et quelques semaines ne prouvent rien. Le workflow force
`ALPACA_PAPER=true`. Passer en argent réel demande une modification volontaire (`ALPACA_PAPER=false`
et `LIVE_TRADING_CONFIRMATION=JE_COMPRENDS_LES_RISQUES`), et ce n'est pas recommandé.
Ce projet est un outil d'expérimentation, pas un conseil en investissement.
