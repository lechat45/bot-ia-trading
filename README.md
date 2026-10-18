# Bot IA trading — le système d'Aywen avec 3 Gemini + 3 Groq sur Alpaca

Reprise de l'expérience d'Aywen (« J'ai laissé 4 IA investir en bourse ») : des IA transformées
en **agents** grâce à des **outils** (actualité, screener, données financières, réseaux, notes,
broker) et des **skills** (un socle commun et une stratégie différente par IA). Ici, 6 agents
gratuits travaillent **en équipe sur un seul compte Alpaca**, en **paper trading** (argent virtuel).

## L'équipe

| Agent | IA | Rôle (inspiré de la vidéo) |
|---|---|---|
| Analyste Qualité | Gemini clé 1 | style « Claude » : chiffres, patience |
| Analyste Équilibre | Gemini clé 2 | style « ChatGPT » : diversification |
| Analyste Sentiment | Groq clé 1 | style « Grok » : humeur du marché, risque accepté |
| Analyste Contrarien | Groq clé 2 | style « Mistral » : titres en forte baisse, en évitant ses erreurs |
| Critique | Groq clé 3 | avocat du diable : dates, paris corrélés, règles |
| Gérant | Gemini clé 3 | décision finale, vérifie avec Google Search |

Si une clé est limitée ou en panne, le routeur passe sur les autres clés du même fournisseur,
puis sur l'autre fournisseur : les 6 clés se relaient.

## Déroulé d'une session (2 par jour ouvré, comme Aywen)

1. **Sélection** : chaque analyste lit ses notes, le portefeuille, le screener (plus fortes
   hausses et baisses, plus gros volumes, tendances Reddit) et l'actualité, puis choisit jusqu'à 4 titres.
2. **Données** : le code récupère pour ces titres le graphique (moyennes mobiles, RSI, ATR,
   performances), les fondamentaux (yfinance), le nombre de jours avant les résultats **calculé par
   le code** (Mistral s'était trompé dans ses dates dans la vidéo), l'actualité et les mentions Reddit.
3. **Thèses** : chaque analyste propose des ordres argumentés (stop, objectif de gain, invalidation, confiance).
4. **Critique** : chaque proposition reçoit un verdict : ok, réserve ou rejet.
5. **Gérant** : décision finale.
6. **Garde-fous codés en dur** ([bot/risk.py](bot/risk.py)), que les IA ne peuvent pas contourner :
   10 % maximum par titre, 10 % de cash minimum, 12 positions au plus, 4 ordres par session,
   stop obligatoire entre 1 et 15 % sous le prix, ratio gain/perte d'au moins 1,5, pas d'action
   sous 5 $, **un stop ne se descend jamais**, pas de rachat d'un titre vendu il y a moins de 2 jours,
   pas de vente d'un titre acheté le jour même.
7. Les achats partent en **ordre bracket** chez Alpaca (achat, stop loss et objectif de gain
   automatiques). Les notes des agents, le journal et un rapport lisible sont enregistrés dans
   [memoire/](memoire/).

## Interface (tableau de bord)

Comme le tableau de bord d'Aywen, l'interface montre la valeur du portefeuille avec sa courbe,
les 6 agents (avec celui qui réfléchit en ce moment), une session en direct étape par étape,
les positions avec leur stop et leur objectif, et l'historique complet des sessions :
raisonnement de chaque agent, verdicts du critique, décision du gérant, ordres envoyés ou
rejetés, consommation de chaque clé.

```bash
python dashboard.py
```

Elle s'ouvre sur http://127.0.0.1:8000 et reste visible uniquement sur ton ordinateur. Le bouton
« Lancer une simulation » fait travailler l'équipe sans envoyer d'ordre. Le bouton « Session
réelle » envoie de vrais ordres sur le compte Alpaca (paper), après confirmation. Sans clés dans
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

Remplis `.env`, puis lance une simulation (les IA réfléchissent mais rien n'est envoyé ; `--force`
permet de tourner même bourse fermée) :

```bash
python main.py --dry-run --force
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
4. Ensuite, le bot tourne seul du lundi au vendredi vers **17 h 05** et **20 h 35** (heure de Paris).

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

Coût : **0 €** dans les deux cas. Un dépôt privé dispose de 2 000 minutes Actions gratuites par
mois, et le bot en utilise environ 300.

## Fichiers

- [main.py](main.py) : lance une session
- [dashboard.py](dashboard.py) et [dashboard/](dashboard/) : l'interface ; [build_site.py](build_site.py) : sa version en ligne
- [check_keys.py](check_keys.py) : vérifie les clés du `.env` sans les afficher
- [bot/agents.py](bot/agents.py) : l'équipe et le déroulé de la session
- [bot/llm.py](bot/llm.py) : Gemini et Groq, rotation des clés, choix automatique du modèle
- [bot/alpaca.py](bot/alpaca.py) : broker et données de marché gratuites (flux IEX)
- [bot/tools.py](bot/tools.py) : indicateurs, fondamentaux, Reddit
- [bot/risk.py](bot/risk.py) et [bot/executor.py](bot/executor.py) : garde-fous et envoi des ordres
- [skills/](skills/) : socle commun et stratégies (modifie-les pour changer le comportement des agents)
- [tests/test_risk.py](tests/test_risk.py) : tests des garde-fous

## À lire avant tout

La conclusion d'Aywen : les gains de son expérience relèvent surtout de la **chance**. Les IA ne
vont pas plus vite que le marché, et 28 jours ne prouvent rien. Le workflow force
`ALPACA_PAPER=true`. Passer en argent réel demande une modification volontaire (`ALPACA_PAPER=false`
et `LIVE_TRADING_CONFIRMATION=JE_COMPRENDS_LES_RISQUES`), et ce n'est pas recommandé.
Ce projet est un outil d'expérimentation, pas un conseil en investissement.
