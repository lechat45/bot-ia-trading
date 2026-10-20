"""Les outils des IA, comme dans la vidéo d'Aywen : Actualité, Screener, Données boursières,
Navigateur web, Réseaux sociaux, Notes et Broker — plus la lecture des skills.

Chaque IA de l'équipe décide seule lesquels appeler et quand. Selon son rôle, elle a en plus :
  - analyste : proposer_ordre (une idée argumentée, vérifiée par les garde-fous) ;
  - critique : donner_avis (ok, réserve ou rejet sur chaque proposition) ;
  - gérant   : passer_ordre, annuler_ordre, ajuster_stop (le broker, sur le compte de l'équipe).
Chaque appel est exécuté ici, journalisé (le « cerveau » du tableau de bord) et renvoyé à l'IA.
"""
import concurrent.futures as cf
import datetime as dt
import json
import logging
import re
import threading
import time
from pathlib import Path

from . import classement, memory, tools
from .alpaca import AlpacaError
from .risk import SYMBOL_RE, check_buy, check_sell, check_stop, clean_symbol, montant_selon_risque
from .universe import EUROPE_ADR, UNIVERSE

log = logging.getLogger("outils")
SKILLS = Path(__file__).resolve().parent.parent / "skills"
MAX_RESULT = 3500

SKILL_INFO = {  # fiches détaillées lues à la demande (le socle commun et la stratégie sont déjà donnés)
    "fonctionnement-du-marche": "horaires, exécution, gaps, moteurs des cours",
    "contexte-macro": "lire le résumé du marché, dates macro",
    "lecture-graphique": "lire historique_prix (tendance, RSI, ATR)",
    "analyse-fondamentale": "lire donnees_financieres, signaux d'alerte",
    "resultats-d-entreprise": "avant et après des résultats",
    "actualite-et-catalyseurs": "juger une info, dater, rappels",
    "recherche-web": "recherche_web et lire_page efficaces",
    "sentiment-reseaux": "Reddit, emballements, manipulations",
    "these-d-investissement": "thèse complète, confiance",
    "taille-de-position": "montant selon risque et stop",
    "stop-loss-take-profit": "stop, objectif, stop suiveur",
    "gestion-du-risque": "contrôle avant achat, portefeuille",
    "sortie-et-suivi": "vendre, alléger, garder ; autopsie",
    "biais-et-erreurs": "pièges de raisonnement",
    "execution-des-ordres": "utiliser les ordres, refus fréquents",
    "notes-et-memoire": "modèles de notes, bonnes leçons",
}
SCREEN_CHOICES = list(tools.SCREENS) + list(tools.STRATEGY_SCREENS) + ["plus_actives", "tendances_reddit", "europe_adr"]


def _str(x) -> str:
    s = json.dumps(x, ensure_ascii=False, separators=(",", ":"), default=str)
    return s if len(s) <= MAX_RESULT else s[:MAX_RESULT] + "…(tronqué)"


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------- déclarations des outils
def declarations(role: str, market_open: bool) -> list[dict]:
    S = {"type": "string"}
    N = {"type": "number"}
    order_props = {
        "action": {"type": "string", "enum": ["acheter", "vendre"]},
        "symbole": S,
        "montant_usd": {"type": "number", "description": "achat, en dollars ; absent : calculé selon confiance et stop"},
        "pourcentage": {"type": "number", "description": "vente : % de la position (100 = tout)"},
        "stop_loss_pct": {"type": "number", "description": "achat : % sous le prix d'achat"},
        "take_profit_pct": {"type": "number", "description": "achat : % au-dessus du prix d'achat"},
        "these": {"type": "string", "description": "faits datés, risques, invalidation, horizon"},
    }
    research = [
        {"name": "lire_skill", "description": "Lit une fiche de savoir-faire.",
         "parameters": {"type": "object", "properties": {"nom": {"type": "string", "enum": list(SKILL_INFO)}},
                        "required": ["nom"]}},
        {"name": "consulter_portefeuille",
         "description": "Le compte de l'équipe : liquidités, positions, ordres planifiés, limites restantes.",
         "parameters": {"type": "object", "properties": {}}},
        {"name": "screener",
         "description": "Classe les actions selon un critère (~170 grandes valeurs ; marché entier pour plus_actives et tendances_reddit).",
         "parameters": {"type": "object", "properties": {
             "critere": {"type": "string", "enum": SCREEN_CHOICES},
             "limite": {"type": "integer", "description": "défaut 10, max 20"}},
             "required": ["critere"]}},
        {"name": "historique_prix",
         "description": "Cours et indicateurs : performances, moyennes mobiles, RSI, ATR, plus haut sur 1 an, comparaison au S&P 500.",
         "parameters": {"type": "object", "properties": {"symbole": S}, "required": ["symbole"]}},
        {"name": "donnees_financieres",
         "description": "Santé de l'entreprise : secteur, croissance, marges, dette, valorisation, date des résultats.",
         "parameters": {"type": "object", "properties": {"symbole": S}, "required": ["symbole"]}},
        {"name": "comparer_titres",
         "description": "Compare 2 à 5 actions côte à côte : tendance, valorisation, croissance, résultats.",
         "parameters": {"type": "object", "properties": {"symboles": {"type": "string", "description": "ex. AAPL, MSFT"}},
                        "required": ["symboles"]}},
        {"name": "historique_idees",
         "description": "Idées d'achat déjà proposées par l'équipe (sur un titre, ou les dernières) : avis, achat, rendement depuis.",
         "parameters": {"type": "object", "properties": {"symbole": S}}},
        {"name": "analystes_et_inities",
         "description": "Révisions des estimations et des notes des analystes (30 j), achats et ventes des dirigeants (6 mois), vente à découvert.",
         "parameters": {"type": "object", "properties": {"symbole": S}, "required": ["symbole"]}},
        {"name": "actualites",
         "description": "Fil d'actualité financière en direct ; sans symbole, celles du marché.",
         "parameters": {"type": "object", "properties": {"symbole": S, "limite": {"type": "integer"}}}},
        {"name": "recherche_web",
         "description": "Recherche Google pour une question précise (en anglais pour une action américaine).",
         "parameters": {"type": "object", "properties": {"question": S}, "required": ["question"]}},
        {"name": "sentiment_reseaux",
         "description": "Mentions Reddit sur 24 h et leur évolution, articles récents.",
         "parameters": {"type": "object", "properties": {"symbole": S}, "required": ["symbole"]}},
        {"name": "ecrire_notes",
         "description": "Réécrit ENTIÈREMENT tes notes (ta mémoire entre deux séances).",
         "parameters": {"type": "object", "properties": {"contenu": S}, "required": ["contenu"]}},
        {"name": "noter_lecon",
         "description": "Ajoute une règle durable à la mémoire longue de l'équipe (2 par séance).",
         "parameters": {"type": "object", "properties": {"lecon": {"type": "string", "description": "300 caractères max"}},
                        "required": ["lecon"]}},
    ]
    research += [
        {"name": "lire_page",
         "description": "Ouvre une page web précise et en lit le texte.",
         "parameters": {"type": "object", "properties": {"url": {"type": "string", "description": "https://…"}},
                        "required": ["url"]}},
        {"name": "creer_rappel",
         "description": "Crée un rappel daté, présenté à toute l'équipe le jour venu.",
         "parameters": {"type": "object", "properties": {
             "date": {"type": "string", "description": "AAAA-MM-JJ"},
             "titre": S, "details": {"type": "string", "description": "ce qu'il faudra vérifier et faire"},
             "symbole": S, "seance": {"type": "string", "enum": ["preparation", "suivi", "toutes"]}},
             "required": ["date", "titre"]}},
        {"name": "voir_rappels", "description": "Liste les rappels actifs.",
         "parameters": {"type": "object", "properties": {}}},
        {"name": "terminer_rappel", "description": "Marque un rappel comme traité.",
         "parameters": {"type": "object", "properties": {"id": S, "note": S}, "required": ["id"]}},
    ]
    end = [{"name": "terminer_session", "description": "Termine ta séance avec ton compte rendu.",
            "parameters": {"type": "object", "properties": {"compte_rendu": S}, "required": ["compte_rendu"]}}]
    if role == "analyste":
        extra = [{"name": "proposer_ordre",
                  "description": "Propose un ordre au gérant ; les garde-fous la vérifient tout de suite.",
                  "parameters": {"type": "object", "properties": {
                      **order_props, "confiance": {"type": "string", "enum": ["faible", "moyen", "eleve"]}},
                      "required": ["action", "symbole", "these"]}}]
    elif role == "critique":
        extra = [{"name": "donner_avis", "description": "Donne ton verdict sur une proposition des analystes.",
                  "parameters": {"type": "object", "properties": {
                      "id": {"type": "string", "description": "identifiant de la proposition, ex. qualite-1"},
                      "verdict": {"type": "string", "enum": ["ok", "reserve", "rejet"]},
                      "raison": S}, "required": ["id", "verdict", "raison"]}}]
    else:  # gérant : le broker
        order_desc = ("Passe un ordre sur le compte de l'équipe. "
                      + ("Bourse OUVERTE : exécution immédiate." if market_open else
                         "Bourse FERMÉE : ordre PLANIFIÉ, exécuté à l'ouverture de New York."))
        extra = [
            {"name": "passer_ordre", "description": order_desc,
             "parameters": {"type": "object", "properties": {
                 **order_props, "source": {"type": "string", "description": "id de la proposition retenue (ex. qualite-1), si c'en est une"},
                 "confiance": {"type": "string", "enum": ["faible", "moyen", "eleve"]}},
                 "required": ["action", "symbole", "these"]}},
            {"name": "annuler_ordre", "description": "Annule un ordre planifié (pas encore exécuté) sur ce titre.",
             "parameters": {"type": "object", "properties": {"symbole": S}, "required": ["symbole"]}},
            {"name": "ajuster_stop", "description": "Remonte le stop loss d'une position (jamais le descendre).",
             "parameters": {"type": "object", "properties": {"symbole": S, "nouveau_stop": N},
                            "required": ["symbole", "nouveau_stop"]}},
        ]
    return research + extra + end


# ---------------------------------------------------------------------- données partagées
class Market:
    """Données de marché partagées par toute l'équipe pendant une séance (téléchargées une seule fois)."""

    def __init__(self, alpaca, offline: bool, today: dt.date):
        self.alpaca, self.offline, self.today = alpaca, offline, today
        self.lock = threading.Lock()
        self._bars: dict = {}
        self._universe = False
        self._fund: dict = {}
        self._analysts: dict = {}
        self._prices: dict = {}
        self._prices_ts = 0.0

    def bars(self, symbols: list[str]) -> dict:
        with self.lock:
            missing = [s for s in symbols if s not in self._bars]
            if missing:
                try:
                    got = self.alpaca.bars(missing)
                except AlpacaError as e:
                    log.warning("historiques indisponibles : %s", e)
                    got = {}
                for s in missing:
                    self._bars[s] = got.get(s, [])
            return {s: self._bars[s] for s in symbols}

    def universe(self) -> dict:
        if not self._universe:
            self.bars(UNIVERSE)
            self._universe = True
        return {s: self._bars.get(s, []) for s in UNIVERSE}

    def prices(self, symbols: list[str]) -> dict:
        symbols = [s for s in symbols if s]
        with self.lock:
            if time.time() - self._prices_ts > 60:
                self._prices, self._prices_ts = {}, time.time()
            missing = [s for s in symbols if s not in self._prices]
        if missing:
            try:
                got = self.alpaca.latest_prices(missing)
            except AlpacaError:
                got = {}
            with self.lock:
                self._prices.update(got)
        return {s: self._prices[s] for s in symbols if s in self._prices}

    def price(self, sym):
        return self.prices([sym]).get(sym)

    def fundamentals(self, sym):
        return self._cached(self._fund, sym, lambda: tools.fundamentals(sym, self.today))

    def analysts(self, sym):
        return self._cached(self._analysts, sym, lambda: tools.analysts_insiders(sym))

    def _cached(self, cache: dict, sym, fetch):
        """Données Yahoo Finance, téléchargées une seule fois par séance pour toute l'équipe."""
        if self.offline:
            return None
        with self.lock:
            if sym in cache:
                return cache[sym]
        value = fetch()
        with self.lock:
            cache[sym] = value
        return value


# ---------------------------------------------------------------------- exécution des outils d'une IA
class AgentEnv:
    def __init__(self, session, agent):
        self.s, self.a = session, agent
        self.acct = session.account  # le compte unique de l'équipe
        self.steps: list[dict] = []
        self.orders: list[dict] = []  # ordres passés (gérant)
        self.proposals: list[dict] = []  # propositions (analyste)
        self.avis: list[dict] = []  # verdicts (critique)
        self.tool_calls = 0
        self.web_left = session.cfg.max_web_searches
        self.pages_left = 4
        self.lecons_left = 2
        self.done = False
        self.compte_rendu = ""

    def log(self, kind, **kw):
        self.steps.append({"t": _now(), "type": kind, **kw})

    def run(self, name: str, args: dict) -> str:
        self.tool_calls += 1
        short = ", ".join(f"{v}" for v in list((args or {}).values())[:2] if not isinstance(v, (dict, list)))[:60]
        memory.state_agent(self.a.id, statut="outil", action=f"{name}({short})", etapes=self.tool_calls)
        allowed = {d["name"] for d in declarations(self.a.role, self.s.market_open)}
        fn = getattr(self, f"t_{name}", None) if name in allowed else None
        try:
            out = fn(**(args or {})) if fn else {"erreur": f"outil « {name} » indisponible pour ton rôle"}
        except TypeError as e:
            out = {"erreur": f"paramètres invalides : {e}"}
        except Exception as e:  # un outil en panne ne doit pas arrêter la séance
            log.exception("outil %s", name)
            out = {"erreur": f"outil indisponible : {str(e)[:150]}"}
        text = out if isinstance(out, str) else _str(out)
        shown = {k: (v[:4000] + "…" if isinstance(v, str) and len(v) > 4000 else v) for k, v in (args or {}).items()}
        step = {"nom": name, "args": shown, "resultat": text[:600]}
        # Le résultat complet est gardé pour le Bureau du tableau de bord (ce que l'IA a lu).
        if isinstance(out, (dict, list)) and name != "lire_skill":
            raw = json.dumps(out, ensure_ascii=False, default=str)
            if len(raw) <= 15000:
                step["donnees"] = out
        self.log("outil", **step)
        return text

    # -------------------------------------------------- skills
    def t_lire_skill(self, nom=""):
        p = SKILLS / "commun" / f"{nom}.md"
        return p.read_text(encoding="utf-8") if nom in SKILL_INFO and p.exists() else {"erreur": "skill inconnu"}

    # -------------------------------------------------- portefeuille
    def valuation(self):
        c = self.s.comptes
        held = list(c.agent(self.acct)["positions"])
        return c.valuation(self.acct, self.s.market.prices(held))

    def planned(self):
        return [o for o in self.s.plan.get("ordres", []) if o.get("compte") == self.acct and o["statut"] == "en_attente"]

    def reserved(self):
        return sum(o.get("montant_usd", 0) for o in self.planned() if o["action"] == "acheter")

    def sector_of(self, sym):
        return tools.INDUSTRIES.get(sym, {}).get("secteur") or (self.s.market.fundamentals(sym) or {}).get("secteur")

    def t_consulter_portefeuille(self):
        v = self.valuation()
        cfg = self.s.cfg
        return {
            **v,
            **tools.portfolio_risk(v, self.sector_of),
            "ordres_planifies_pour_ouverture": [{k: o.get(k) for k in ("action", "symbole", "montant_usd", "pourcentage",
                                                                       "stop_loss_pct", "take_profit_pct")} for o in self.planned()],
            "limites": {
                "max_par_titre_usd": round(v["valeur"] * cfg.max_position_pct / 100, 0),
                "liquidites_utilisables_usd": round(max(0, v["cash"] - self.reserved() - v["valeur"] * cfg.min_cash_pct / 100), 0),
                "positions_max": cfg.max_positions,
                "max_par_secteur_pct": cfg.max_sector_pct,
                "frein_d_urgence": self.s.frein or "inactif",
                "stop_loss_pct": f"entre {cfg.min_stop_distance_pct:g} et {cfg.max_stop_distance_pct:g}",
                "ratio_gain_perte_min": cfg.min_reward_risk,
            },
        }

    # -------------------------------------------------- screener
    def t_screener(self, critere="baisse_semaine", limite=10):
        limite = max(1, min(int(_num(limite) or 10), 20))
        mk, mn = self.s.market, self.s.cfg.min_price
        if critere in tools.STRATEGY_SCREENS:
            return tools.screen_strategy(mk.universe(), critere, limite)
        if critere == "plus_actives":
            rows = self.s.alpaca.most_actives(40)
            syms = [r["symbol"] for r in rows if SYMBOL_RE.match(r["symbol"])]
            px = mk.prices(syms)
            return [{"s": r["symbol"], "prix": round(px[r["symbol"]], 2), "volume": r.get("volume")} for r in rows
                    if px.get(r["symbol"], 0) >= mn][:limite]
        if critere == "tendances_reddit":
            data = sorted(tools.reddit_trending().values(), key=lambda x: x.get("rank", 999)) if not mk.offline else []
            return [{"s": x["ticker"], "nom": x.get("name"), "mentions_24h": x.get("mentions"),
                     "mentions_veille": x.get("mentions_24h_ago")} for x in data[:limite]] or {"info": "indisponible"}
        if critere in ("hausse_jour", "baisse_jour"):
            try:
                mv = self.s.alpaca.movers(40)
                key = "gainers" if critere == "hausse_jour" else "losers"
                rows = [{"s": m["symbol"], "var_pct": round(m.get("percent_change", 0), 1), "prix": m.get("price")}
                        for m in mv.get(key, []) if (m.get("price") or 0) >= mn and SYMBOL_RE.match(m["symbol"])]
                if rows:
                    return rows[:limite]
            except AlpacaError:
                pass
        if critere == "europe_adr":
            res = tools.screen(mk.universe(), "baisse_mois", 50, only=set(EUROPE_ADR))
            return sorted(res, key=lambda r: r["perf_1m_pct"] or 0)[:limite]
        if critere not in tools.SCREENS:
            return {"erreur": f"critère inconnu, choix : {', '.join(SCREEN_CHOICES)}"}
        return tools.screen(mk.universe(), critere, limite)

    # -------------------------------------------------- données
    def t_historique_prix(self, symbole=""):
        sym = clean_symbol(symbole)
        bars = self.s.market.bars([sym]).get(sym) or []
        if not bars:
            return {"erreur": f"aucun historique pour {sym}"}
        out = tools.price_history(bars)
        spy = self.s.market.bars(["SPY"]).get("SPY") or []
        if spy:
            ind = tools.indicators(spy)
            out["marche_SPY"] = {k: ind.get(k) for k in ("perf_5j_pct", "perf_1m_pct", "perf_3m_pct")}
        live = self.s.market.price(sym)
        if live:
            out["dernier_prix"] = round(live, 2)
        out["niveaux"] = tools.levels(bars, live or out.get("prix"))
        # comparaison au fonds de son secteur, pas seulement au S&P 500
        sect = tools.INDUSTRIES.get(sym, {}).get("secteur") or (self.s.market.fundamentals(sym) or {}).get("secteur")
        etf = tools.SECTOR_ETF.get(sect)
        eb = self.s.market.bars([etf]).get(etf) if etf and etf != sym else None
        if eb:
            e, me = tools.indicators(eb), out
            row = {"fonds": etf, "secteur": sect}
            for k in ("perf_1m_pct", "perf_3m_pct"):
                if e.get(k) is not None and me.get(k) is not None:
                    row[f"secteur_{k}"] = e[k]
                    row[f"ecart_{k[5:7]}_points"] = round(me[k] - e[k], 1)
            out["vs_secteur"] = row
        return out

    def t_donnees_financieres(self, symbole=""):
        sym = clean_symbol(symbole)
        f = self.s.market.fundamentals(sym)
        if not f:
            return {"erreur": f"données financières de {sym} indisponibles"}
        names = tools.peers(sym, f.get("secteur"), f.get("industrie"))
        if names:  # les concurrents, téléchargés en parallèle (et gardés pour toute l'équipe)
            with cf.ThreadPoolExecutor(max_workers=4) as pool:
                funds = dict(zip(names, pool.map(self.s.market.fundamentals, names)))
            comp = tools.peer_comparison(f, funds)
            if comp:
                f = {**f, "comparaison_concurrents": comp}
        return f

    def t_analystes_et_inities(self, symbole=""):
        sym = clean_symbol(symbole)
        return self.s.market.analysts(sym) or {"erreur": f"données des analystes et des dirigeants de {sym} indisponibles"}

    def t_actualites(self, symbole="", limite=8):
        sym = clean_symbol(symbole) if symbole else None
        limite = max(1, min(int(_num(limite) or 8), 15))
        news = self.s.alpaca.news([sym] if sym else None, limit=limite)
        out = [{"date": n.get("created_at", "")[:16].replace("T", " "), "titre": n.get("headline", ""),
                "resume": (n.get("summary") or "")[:220], "source": n.get("source"),
                "symboles": n.get("symbols", [])[:5]} for n in news]
        if sym and not self.s.market.offline:  # Google Actualités : la grande presse, en plus du fil d'Alpaca
            name = (self.s.market.fundamentals(sym) or {}).get("nom")
            try:
                seen = {o["titre"] for o in out}
                out += [{"date": g["date"], "titre": g["titre"], "source": f"{g['source']} (Google Actualités)"}
                        for g in tools.google_news(f"{name} {sym}" if name else f"{sym} stock", limit=5)
                        if g["titre"] not in seen]
            except Exception as e:
                log.info("Google Actualités %s : %s", sym, e)
        return out or {"info": "aucune actualité récente"}

    def t_comparer_titres(self, symboles=""):
        raw = ",".join(symboles) if isinstance(symboles, list) else str(symboles)
        syms = list(dict.fromkeys(clean_symbol(s) for s in re.split(r"[,;\s]+", raw) if s.strip()))[:5]
        if len(syms) < 2:
            return {"erreur": "donne 2 à 5 symboles séparés par des virgules, ex. « AAPL, MSFT, GOOGL »"}
        bars = self.s.market.bars(syms)
        with cf.ThreadPoolExecutor(max_workers=5) as pool:
            funds = dict(zip(syms, pool.map(self.s.market.fundamentals, syms)))
        rows = []
        for s in syms:
            ind, f = tools.indicators(bars.get(s) or []), funds.get(s) or {}
            row = {"s": s, "secteur": f.get("secteur"),
                   **{k: ind.get(k) for k in ("prix", "perf_1m_pct", "perf_3m_pct", "rsi14", "ecart_plus_haut_pct")}}
            if ind.get("prix") and ind.get("sma200"):
                row["au_dessus_sma200"] = ind["prix"] > ind["sma200"]
            if ind.get("prix") and ind.get("atr14"):
                row["atr_pct"] = round(ind["atr14"] / ind["prix"] * 100, 1)
            row.update({k: f[k] for k in ("per_attendu", "croissance_ca_pct", "marge_op_pct", "roe_pct", "dette_sur_fp",
                                          "jours_avant_resultats") if f.get(k) is not None})
            rows.append({k: v for k, v in row.items() if v is not None})
        return {"comparaison": rows}

    def t_historique_idees(self, symbole=""):
        sym = clean_symbol(symbole) if symbole else None
        props = [p for p in classement.load_propositions() if not sym or p["symbole"] == sym][-10:]
        if not props:
            return {"info": f"l'équipe n'a encore jamais proposé {sym}" if sym else "aucune idée passée"}
        prices = self.s.market.prices(sorted({p["symbole"] for p in props}))
        return [{"date": p.get("date"), "auteur": p.get("auteur"), "symbole": p["symbole"],
                 "avis_critique": p.get("verdict"), "achetee": bool(p.get("retenue")), "prix_du_jour": p["prix_ref"],
                 "rendement_depuis_pct": round((prices[p["symbole"]] / p["prix_ref"] - 1) * 100, 1)
                 if prices.get(p["symbole"]) else None} for p in reversed(props)]

    def t_recherche_web(self, question=""):
        if self.web_left <= 0:
            return {"erreur": "budget de recherches web épuisé pour cette séance : note l'information comme inconnue"}
        self.web_left -= 1
        res = self.s.router.web_search(question, who=self.a.id)
        if res.pop("cache", False):  # réponse déjà connue de l'équipe : ne compte pas dans le budget
            self.web_left += 1
        res["recherches_restantes"] = self.web_left
        return res

    def t_sentiment_reseaux(self, symbole=""):
        sym = clean_symbol(symbole)
        out = {"symbole": sym}
        if not self.s.market.offline:
            out["reddit"] = tools.reddit_sentiment(sym) or "indisponible"
        try:
            news = self.s.alpaca.news([sym], limit=50)
            since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=3)).isoformat()
            out["articles_3_derniers_jours"] = sum(1 for n in news if n.get("created_at", "") >= since)
        except AlpacaError:
            pass
        if not self.s.market.offline and tools.reddit_oauth_configured():
            out["messages_reddit"] = tools.reddit_posts(sym) or "aucun message récent"
        out["note"] = "X/Twitter n'a pas d'accès gratuit : utilise recherche_web si nécessaire."
        return out

    def t_lire_page(self, url=""):
        if self.pages_left <= 0:
            return {"erreur": "budget de pages web épuisé pour cette séance"}
        if self.s.market.offline:
            return {"erreur": "navigateur indisponible en test hors-ligne"}
        self.pages_left -= 1
        res = tools.read_page(url)
        res["pages_restantes"] = self.pages_left
        return res

    # -------------------------------------------------- notes
    def t_ecrire_notes(self, contenu=""):
        if not contenu.strip():
            return {"erreur": "notes vides"}
        if not self.s.dry_run:
            memory.write_notes(self.a.id, contenu, self.s.when)
        self.s.new_notes[self.a.id] = contenu
        return {"ok": True, "caracteres": len(contenu[:memory.MAX_NOTES]),
                "info": "notes enregistrées" if not self.s.dry_run else "notes gardées (simulation : non enregistrées)"}

    def t_noter_lecon(self, lecon=""):
        texte = " ".join(str(lecon).split())
        if len(texte) < 15:
            return {"refuse": "leçon trop courte : écris une règle concrète et réutilisable"}
        if self.lecons_left <= 0:
            return {"refuse": "2 leçons maximum par séance"}
        self.lecons_left -= 1
        self.s.add_lecon({"date": self.s.trading_date, "auteur": self.a.id, "texte": texte[:300]})
        return {"ok": True, "info": "leçon ajoutée à la mémoire de l'équipe" if not self.s.dry_run
                else "leçon gardée (simulation : non enregistrée)"}

    # -------------------------------------------------- analyste : proposer
    def _check(self, action, sym, montant_usd, pourcentage, stop_loss_pct, take_profit_pct, clamp=False):
        val = self.valuation()
        if action == "acheter":
            ctx = self.s.buy_context(sym, val, self.planned())
            return check_buy(self.s.cfg, self.acct, val, sym, self.s.market.price(sym), montant_usd, stop_loss_pct,
                             take_profit_pct, self.s.journal, reserved=self.reserved(), clamp=clamp, **ctx)
        if action in ("vendre", "alleger"):
            return check_sell(self.s.cfg, self.acct, val, sym, pourcentage, self.s.journal)
        return False, "action inconnue : acheter ou vendre", {}

    def t_proposer_ordre(self, action="", symbole="", montant_usd=None, pourcentage=None, stop_loss_pct=None,
                         take_profit_pct=None, these="", confiance=""):
        sym, action = clean_symbol(symbole), str(action).lower().strip()
        if len(self.proposals) >= 3:
            return {"refuse": "3 propositions maximum par séance : garde les meilleures idées"}
        if any(p["symbole"] == sym for p in self.proposals):
            return {"refuse": "tu as déjà proposé ce titre"}
        montant_usd, auto = self._auto_amount(action, montant_usd, stop_loss_pct, confiance)
        # Les montants sont vérifiés comme pour un vrai ordre, mais ramenés aux limites plutôt que refusés :
        # c'est le gérant qui décidera de la taille finale.
        ok, msg, d = self._check(action, sym, montant_usd, pourcentage, stop_loss_pct, take_profit_pct, clamp=True)
        if not ok:
            self.log("refus", symbole=sym, raison=msg)
            return {"refuse": msg}
        pid = f"{self.a.id}-{len(self.proposals) + 1}"
        p = {"id": pid, "auteur": self.a.id, "action": action, "symbole": sym, "these": these[:1500],
             "confiance": confiance, **{k: d.get(k) for k in ("montant", "qty", "prix_ref", "stop_loss_pct",
                                                              "take_profit_pct", "pourcentage") if d.get(k) is not None}}
        self.proposals.append(p)
        self.s.add_proposal(p)
        return {"ok": True, "id": pid, "message": f"Proposition {pid} transmise au critique puis au gérant.",
                **self._risk_summary(d, auto)}

    def _auto_amount(self, action, montant_usd, stop_loss_pct, confiance):
        """Montant facultatif pour un achat : sans montant, le code le calcule selon la confiance et le stop."""
        if action != "acheter" or (_num(montant_usd) or 0) > 0:
            return montant_usd, False
        m = montant_selon_risque(self.valuation()["valeur"], stop_loss_pct, confiance)
        return (m, True) if m else (montant_usd, False)

    def _risk_summary(self, d: dict, auto: bool) -> dict:
        """Ce que l'achat risque vraiment : perte si le stop est touché, en % du compte, et ratio gain/perte."""
        if not d.get("montant") or not d.get("stop_loss_pct"):
            return {}
        value = self.valuation()["valeur"] or 1
        out = {"risque_pct_du_compte": round(d["montant"] * d["stop_loss_pct"] / value, 2),
               "ratio_gain_perte": round(d["take_profit_pct"] / d["stop_loss_pct"], 2)}
        if auto:
            out["montant_calcule"] = (f"{d['montant']:.0f} $ calculés par le code selon ta confiance et ton stop "
                                      "(fiche taille-de-position), ramenés aux limites si besoin")
        return out

    # -------------------------------------------------- critique : avis
    def t_donner_avis(self, id="", verdict="", raison=""):
        if not any(p["id"] == id for p in self.s.proposals):
            return {"erreur": f"proposition « {id} » inconnue ; identifiants : {', '.join(p['id'] for p in self.s.proposals)}"}
        v = {"id": id, "verdict": str(verdict).lower(), "raison": raison[:800]}
        self.avis = [a for a in self.avis if a["id"] != id] + [v]
        self.s.set_avis(v)
        return {"ok": True}

    # -------------------------------------------------- gérant : broker
    def t_passer_ordre(self, action="", symbole="", montant_usd=None, pourcentage=None,
                       stop_loss_pct=None, take_profit_pct=None, these="", source="", confiance=""):
        cfg, sym, action = self.s.cfg, clean_symbol(symbole), str(action).lower().strip()
        if len(self.orders) >= cfg.max_orders:
            return {"refuse": f"maximum {cfg.max_orders} ordres par séance atteint"}
        if any(o["symbole"] == sym for o in self.orders):
            return {"refuse": "un seul ordre par titre et par séance"}
        montant_usd, auto = self._auto_amount(action, montant_usd, stop_loss_pct, confiance)
        ok, msg, d = self._check(action, sym, montant_usd, pourcentage, stop_loss_pct, take_profit_pct, clamp=auto)
        if not ok:
            self.log("refus", symbole=sym, raison=msg)
            return {"refuse": msg}
        record = {"action": action, "symbole": sym, "these": these[:1500], "source": source}
        if not self.s.market_open:
            o = {"compte": self.acct, "agent": self.a.id, "action": action, "symbole": sym, "source": source,
                 "these": these[:1500], "statut": "en_attente", "cree_le": _now(),
                 "prix_reference": d.get("prix_ref") or round(self.s.market.price(sym) or 0, 2)}
            if action == "acheter":
                o.update(montant_usd=d["montant"], qty_estimee=d["qty"], stop_loss_pct=d["stop_loss_pct"],
                         take_profit_pct=d["take_profit_pct"])
                msg = (f"Achat planifié : ~{d['qty']} {sym} (~{d['montant']:.0f} $ au prix de référence {d['prix_ref']} $). "
                       f"Exécution automatique à l'ouverture de New York ; stop à -{d['stop_loss_pct']:g} % et objectif à "
                       f"+{d['take_profit_pct']:g} % du prix d'exécution. Annulé si l'ouverture s'écarte de plus de "
                       f"{cfg.max_gap_pct:g} % de {d['prix_ref']} $.")
            else:
                o.update(pourcentage=d["pourcentage"], qty_estimee=d["qty"])
                msg = f"Vente de {d['qty']} {sym} planifiée pour l'ouverture."
            self.s.add_plan(o)
            self.orders.append({**record, **o, "resultat": "planifié pour l'ouverture"})
            return {"planifie": True, "message": msg, **self._risk_summary(d, auto)}
        if action == "acheter":
            r = self.s.broker.buy(self.acct, sym, d["qty"], d["stop_loss_pct"], d["take_profit_pct"], these[:1500],
                                  source=source)
        else:
            r = self.s.broker.sell(self.acct, sym, d["qty"], these, source=source)
        self.orders.append({**record, **d, "resultat": r["message"], "ok": r["ok"]})
        return {**r, **self._risk_summary(d, auto)} if action == "acheter" else r

    def t_annuler_ordre(self, symbole=""):
        sym = clean_symbol(symbole)
        n = self.s.cancel_plan(self.acct, sym)
        return {"ok": bool(n), "message": f"{n} ordre(s) planifié(s) annulé(s) sur {sym}" if n else "aucun ordre planifié sur ce titre"}

    def t_ajuster_stop(self, symbole="", nouveau_stop=None):
        sym = clean_symbol(symbole)
        ok, msg, d = check_stop(self.s.cfg, self.valuation(), sym, nouveau_stop, self.s.market.price(sym))
        if not ok:
            self.log("refus", symbole=sym, raison=msg)
            return {"refuse": msg}
        r = self.s.broker.adjust_stop(self.acct, sym, d["stop"])
        self.orders.append({"action": "ajuster_stop", "symbole": sym, "stop": d["stop"], "resultat": r["message"],
                            "ok": r["ok"]})
        return r

    # -------------------------------------------------- rappels
    def t_creer_rappel(self, date="", titre="", details="", symbole="", seance="toutes"):
        txt = str(date).strip()
        try:
            d = (dt.date.fromisoformat(txt) if "-" in txt else dt.datetime.strptime(txt, "%d/%m/%Y").date())
        except ValueError:
            return {"refuse": "date invalide : utilise le format AAAA-MM-JJ"}
        today = dt.datetime.now(dt.timezone.utc).date()
        if not today <= d <= today + dt.timedelta(days=180):
            return {"refuse": "la date doit être comprise entre aujourd'hui et dans 180 jours"}
        if not str(titre).strip():
            return {"refuse": "titre obligatoire"}
        with self.s.lock:
            actifs = [r for r in self.s.rappels if r["statut"] == "actif"]
            if len(actifs) >= 30:
                return {"refuse": "30 rappels actifs maximum : termine ceux qui sont traités"}
            rid = f"r{len(self.s.rappels) + 1}-{d.strftime('%m%d')}"
            r = {"id": rid, "date": d.isoformat(), "titre": str(titre)[:200], "details": str(details)[:1000],
                 "symbole": clean_symbol(symbole) if symbole else "", "seance": seance if seance in ("preparation", "suivi") else "toutes",
                 "cree_par": self.a.id, "cree_le": _now(), "statut": "actif"}
            self.s.rappels.append(r)
        return {"ok": True, "id": rid, "message": f"Rappel {rid} créé pour le {d.isoformat()} : il sera présenté à l'équipe ce jour-là."}

    def t_voir_rappels(self):
        actifs = sorted((r for r in self.s.rappels if r["statut"] == "actif"), key=lambda r: r["date"])
        return actifs or {"info": "aucun rappel actif"}

    def t_terminer_rappel(self, id="", note=""):
        with self.s.lock:
            for r in self.s.rappels:
                if r["id"] == id and r["statut"] == "actif":
                    r.update(statut="fait", note=str(note)[:500], fait_par=self.a.id, fait_le=_now())
                    return {"ok": True}
        return {"erreur": f"rappel « {id} » introuvable ou déjà traité"}

    def t_terminer_session(self, compte_rendu=""):
        self.done = True
        self.compte_rendu = compte_rendu.strip()
        return {"ok": True, "message": "Séance terminée."}
