"""Les outils des IA, comme dans la vidéo d'Aywen : Actualité, Screener, Données boursières,
Navigateur web, Réseaux sociaux, Notes et Broker — plus la lecture des skills.

L'IA décide seule lesquels appeler et quand. Chaque appel est exécuté ici, journalisé (pour le
« cerveau » affiché dans le tableau de bord) et son résultat est renvoyé à l'IA.
"""
import datetime as dt
import json
import logging
import threading
import time
from pathlib import Path

from . import memory, tools
from .alpaca import AlpacaError
from .risk import SYMBOL_RE, check_buy, check_sell, check_stop, clean_symbol
from .universe import EUROPE_ADR, UNIVERSE

log = logging.getLogger("outils")
SKILLS = Path(__file__).resolve().parent.parent / "skills"
MAX_RESULT = 3500

SKILL_INFO = {
    "fonctionnement-du-marche": "actions, horaires, événements qui font bouger les cours",
    "lecture-graphique": "tendance, moyennes mobiles, RSI, ATR, limites d'un graphique",
    "analyse-fondamentale": "croissance, marges, dette, valorisation, pièges",
    "actualite-et-catalyseurs": "vérifier une info, dates des catalyseurs",
    "sentiment-reseaux": "utiliser Reddit et les réseaux sans se faire piéger",
    "gestion-du-risque": "taille de position, corrélations, comportements à éviter",
    "stop-loss-take-profit": "placer et gérer stop loss et objectif de gain",
    "execution-des-ordres": "utiliser passer_ordre, ordres planifiés à l'ouverture",
    "notes-et-memoire": "structure des notes entre deux séances",
}
SCREEN_CHOICES = list(tools.SCREENS) + ["plus_actives", "tendances_reddit", "europe_adr"]


def _str(x) -> str:
    s = json.dumps(x, ensure_ascii=False, separators=(",", ":"), default=str)
    return s if len(s) <= MAX_RESULT else s[:MAX_RESULT] + "…(tronqué)"


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------- déclarations des outils
def declarations(market_open: bool) -> list[dict]:
    S = {"type": "string"}
    order_desc = ("Passe un ordre sur TON sous-compte. "
                  + ("La bourse est OUVERTE : exécution immédiate." if market_open else
                     "La bourse est FERMÉE : l'ordre est PLANIFIÉ et sera exécuté automatiquement à l'ouverture "
                     "de New York (15h30 heure de Paris), au prix d'ouverture."))
    return [
        {"name": "lire_skill", "description": "Lit un de tes skills (fiche de savoir-faire) avant d'utiliser un outil.",
         "parameters": {"type": "object", "properties": {"nom": {"type": "string", "enum": list(SKILL_INFO)}},
                        "required": ["nom"]}},
        {"name": "consulter_portefeuille",
         "description": "Ton sous-compte : liquidités, positions (prix d'achat, plus-value, stop, objectif), ordres planifiés, limites.",
         "parameters": {"type": "object", "properties": {}}},
        {"name": "screener",
         "description": ("Filtre les actions selon un critère. Univers : ~170 grandes valeurs US et européennes cotées à "
                         "New York, plus le marché entier pour plus_actives et les tendances Reddit."),
         "parameters": {"type": "object", "properties": {
             "critere": {"type": "string", "enum": SCREEN_CHOICES},
             "limite": {"type": "integer", "description": "nombre de résultats (défaut 10, max 20)"}},
             "required": ["critere"]}},
        {"name": "historique_prix",
         "description": "Historique du cours d'une action : performances, moyennes mobiles, RSI, ATR, plus haut/bas 52 semaines, cours hebdo sur 1 an.",
         "parameters": {"type": "object", "properties": {"symbole": S}, "required": ["symbole"]}},
        {"name": "donnees_financieres",
         "description": "Santé de l'entreprise : secteur, capitalisation, PER, marges, croissance, dette, flux de trésorerie, date des prochains résultats (avec le nombre de jours).",
         "parameters": {"type": "object", "properties": {"symbole": S}, "required": ["symbole"]}},
        {"name": "actualites",
         "description": "Fil d'actualité financière en direct (multi-sources). Sans symbole : les dernières actualités du marché.",
         "parameters": {"type": "object", "properties": {"symbole": S, "limite": {"type": "integer"}}}},
        {"name": "recherche_web",
         "description": "Recherche Google pour une question précise (dirigeant, date d'un événement, déclaration…). Budget limité par séance : pose des questions précises.",
         "parameters": {"type": "object", "properties": {"question": S}, "required": ["question"]}},
        {"name": "sentiment_reseaux",
         "description": "Humeur des réseaux sur une action : mentions Reddit (r/wallstreetbets, r/stocks…) sur 24 h et évolution.",
         "parameters": {"type": "object", "properties": {"symbole": S}, "required": ["symbole"]}},
        {"name": "ecrire_notes",
         "description": "Réécrit ENTIÈREMENT tes notes (ta seule mémoire entre deux séances) : positions et thèses, calendrier daté, liste de surveillance, leçons.",
         "parameters": {"type": "object", "properties": {"contenu": S}, "required": ["contenu"]}},
        {"name": "passer_ordre", "description": order_desc,
         "parameters": {"type": "object", "properties": {
             "action": {"type": "string", "enum": ["acheter", "vendre"]},
             "symbole": S,
             "montant_usd": {"type": "number", "description": "achat : montant à investir en dollars"},
             "pourcentage": {"type": "number", "description": "vente : % de la position à vendre (100 = tout)"},
             "stop_loss_pct": {"type": "number", "description": "achat : stop loss en % sous le prix d'achat"},
             "take_profit_pct": {"type": "number", "description": "achat : objectif de gain en % au-dessus du prix d'achat"},
             "these": {"type": "string", "description": "ta thèse : arguments datés, risques, invalidation, horizon, confiance"}},
             "required": ["action", "symbole", "these"]}},
        {"name": "annuler_ordre", "description": "Annule un ordre planifié (pas encore exécuté) sur ce titre.",
         "parameters": {"type": "object", "properties": {"symbole": S}, "required": ["symbole"]}},
        {"name": "ajuster_stop", "description": "Remonte le stop loss d'une position (jamais le descendre).",
         "parameters": {"type": "object", "properties": {"symbole": S, "nouveau_stop": {"type": "number"}},
                        "required": ["symbole", "nouveau_stop"]}},
        {"name": "terminer_session",
         "description": "Termine ta séance avec ton compte rendu : décisions prises et pourquoi, ce qu'il faut surveiller.",
         "parameters": {"type": "object", "properties": {"compte_rendu": S}, "required": ["compte_rendu"]}},
    ]


# ---------------------------------------------------------------------- données partagées
class Market:
    """Données de marché partagées par les 4 IA d'une séance (téléchargées une seule fois)."""

    def __init__(self, alpaca, offline: bool, today: dt.date):
        self.alpaca, self.offline, self.today = alpaca, offline, today
        self.lock = threading.Lock()
        self._bars: dict = {}
        self._universe = False
        self._fund: dict = {}
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
        if self.offline:
            return None
        with self.lock:
            if sym in self._fund:
                return self._fund[sym]
        f = tools.fundamentals(sym, self.today)
        with self.lock:
            self._fund[sym] = f
        return f


# ---------------------------------------------------------------------- exécution des outils d'une IA
class AgentEnv:
    def __init__(self, session, agent):
        self.s, self.a = session, agent
        self.steps: list[dict] = []
        self.orders: list[dict] = []
        self.tool_calls = 0
        self.web_left = session.cfg.max_web_searches
        self.done = False
        self.compte_rendu = ""

    def log(self, kind, **kw):
        self.steps.append({"t": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "type": kind, **kw})

    def run(self, name: str, args: dict) -> str:
        self.tool_calls += 1
        short = ", ".join(f"{v}" for v in list((args or {}).values())[:2] if not isinstance(v, (dict, list)))[:60]
        memory.state_agent(self.a.id, statut="outil", action=f"{name}({short})", etapes=self.tool_calls)
        fn = getattr(self, f"t_{name}", None)
        try:
            out = fn(**(args or {})) if fn else {"erreur": f"outil inconnu « {name} »"}
        except TypeError as e:
            out = {"erreur": f"paramètres invalides : {e}"}
        except Exception as e:  # un outil en panne ne doit pas arrêter la séance
            log.exception("outil %s", name)
            out = {"erreur": f"outil indisponible : {str(e)[:150]}"}
        text = out if isinstance(out, str) else _str(out)
        shown = {k: (v[:400] + "…" if isinstance(v, str) and len(v) > 400 else v) for k, v in (args or {}).items()}
        self.log("outil", nom=name, args=shown, resultat=text[:600])
        return text

    # -------------------------------------------------- skills
    def t_lire_skill(self, nom=""):
        p = SKILLS / "commun" / f"{nom}.md"
        return p.read_text(encoding="utf-8") if nom in SKILL_INFO and p.exists() else {"erreur": "skill inconnu"}

    # -------------------------------------------------- portefeuille
    def valuation(self):
        c = self.s.comptes
        held = list(c.agent(self.a.id)["positions"])
        return c.valuation(self.a.id, self.s.market.prices(held))

    def planned(self):
        return [o for o in self.s.plan.get("ordres", []) if o["agent"] == self.a.id and o["statut"] == "en_attente"]

    def t_consulter_portefeuille(self):
        v = self.valuation()
        cfg = self.s.cfg
        reserved = sum(o.get("montant_usd", 0) for o in self.planned() if o["action"] == "acheter")
        return {
            **v,
            "ordres_planifies_pour_ouverture": [{k: o.get(k) for k in ("action", "symbole", "montant_usd", "pourcentage",
                                                                       "stop_loss_pct", "take_profit_pct")} for o in self.planned()],
            "limites": {
                "max_par_titre_usd": round(v["valeur"] * cfg.max_position_pct / 100, 0),
                "liquidites_utilisables_usd": round(max(0, v["cash"] - reserved - v["valeur"] * cfg.min_cash_pct / 100), 0),
                "positions_max": cfg.max_positions,
                "ordres_restants_cette_seance": cfg.max_orders - len(self.orders),
                "stop_loss_pct": f"entre {cfg.min_stop_distance_pct:g} et {cfg.max_stop_distance_pct:g}",
                "ratio_gain_perte_min": cfg.min_reward_risk,
            },
        }

    # -------------------------------------------------- screener
    def t_screener(self, critere="baisse_semaine", limite=10):
        limite = max(1, min(int(_num(limite) or 10), 20))
        mk, mn = self.s.market, self.s.cfg.min_price
        if critere == "plus_actives":
            rows = self.s.alpaca.most_actives(40)
            syms = [r["symbol"] for r in rows if SYMBOL_RE.match(r["symbol"])]
            px = mk.prices(syms)
            return [{"s": s, "prix": round(px[s], 2), "volume": r.get("volume")} for r in rows
                    for s in [r["symbol"]] if px.get(s, 0) >= mn][:limite]
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
        return out

    def t_donnees_financieres(self, symbole=""):
        sym = clean_symbol(symbole)
        f = self.s.market.fundamentals(sym)
        return f or {"erreur": f"données financières de {sym} indisponibles"}

    def t_actualites(self, symbole="", limite=8):
        sym = clean_symbol(symbole) if symbole else None
        limite = max(1, min(int(_num(limite) or 8), 15))
        news = self.s.alpaca.news([sym] if sym else None, limit=limite)
        return [{"date": n.get("created_at", "")[:16].replace("T", " "), "titre": n.get("headline", ""),
                 "resume": (n.get("summary") or "")[:220], "source": n.get("source"),
                 "symboles": n.get("symbols", [])[:5]} for n in news] or {"info": "aucune actualité récente"}

    def t_recherche_web(self, question=""):
        if self.web_left <= 0:
            return {"erreur": "budget de recherches web épuisé pour cette séance : note l'information comme inconnue"}
        self.web_left -= 1
        res = self.s.router.web_search(question, who=self.a.id)
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
        out["note"] = "X/Twitter n'a pas d'accès gratuit : utilise recherche_web si nécessaire."
        return out

    # -------------------------------------------------- notes
    def t_ecrire_notes(self, contenu=""):
        if not contenu.strip():
            return {"erreur": "notes vides"}
        if not self.s.dry_run:
            memory.write_notes(self.a.id, contenu, self.s.when)
        self.s.new_notes[self.a.id] = contenu
        return {"ok": True, "caracteres": len(contenu[:memory.MAX_NOTES]),
                "info": "notes enregistrées" if not self.s.dry_run else "notes gardées (simulation : non enregistrées)"}

    # -------------------------------------------------- broker
    def t_passer_ordre(self, action="", symbole="", montant_usd=None, pourcentage=None,
                       stop_loss_pct=None, take_profit_pct=None, these=""):
        cfg, sym, action = self.s.cfg, clean_symbol(symbole), str(action).lower().strip()
        if len(self.orders) >= cfg.max_orders:
            return {"refuse": f"maximum {cfg.max_orders} ordres par séance atteint"}
        if any(o["symbole"] == sym for o in self.orders):
            return {"refuse": "un seul ordre par titre et par séance"}
        val = self.valuation()
        journal = self.s.journal
        record = {"action": action, "symbole": sym, "these": these[:1500]}
        if action == "acheter":
            price = self.s.market.price(sym)
            reserved = sum(o.get("montant_usd", 0) for o in self.planned() if o["action"] == "acheter")
            ok, msg, d = check_buy(cfg, self.a.id, val, sym, price, montant_usd, stop_loss_pct, take_profit_pct,
                                   journal, reserved=reserved)
            if not ok:
                self.log("refus", symbole=sym, raison=msg)
                return {"refuse": msg}
            if not self.s.market_open:
                o = {"agent": self.a.id, "action": "acheter", "symbole": sym, "montant_usd": d["montant"],
                     "qty_estimee": d["qty"], "prix_reference": d["prix_ref"], "stop_loss_pct": d["stop_loss_pct"],
                     "take_profit_pct": d["take_profit_pct"], "these": these[:1500], "statut": "en_attente",
                     "cree_le": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
                self.s.add_plan(o)
                self.orders.append({**record, **o, "resultat": "planifié pour l'ouverture"})
                return {"planifie": True, "message": (
                    f"Achat planifié : ~{d['qty']} {sym} (~{d['montant']:.0f} $ au prix de référence {d['prix_ref']} $). "
                    f"Exécution automatique à l'ouverture de New York ; stop à -{d['stop_loss_pct']:g} % et objectif à "
                    f"+{d['take_profit_pct']:g} % du prix d'exécution. Annulé si l'ouverture s'écarte de plus de "
                    f"{cfg.max_gap_pct:g} % de {d['prix_ref']} $.")}
            r = self.s.broker.buy(self.a.id, sym, d["qty"], d["stop_loss_pct"], d["take_profit_pct"], these[:1500])
            self.orders.append({**record, **d, "resultat": r["message"], "ok": r["ok"]})
            return r
        if action in ("vendre", "alleger"):
            ok, msg, d = check_sell(cfg, self.a.id, val, sym, pourcentage, journal)
            if not ok:
                self.log("refus", symbole=sym, raison=msg)
                return {"refuse": msg}
            if not self.s.market_open:
                o = {"agent": self.a.id, "action": "vendre", "symbole": sym, "pourcentage": d["pourcentage"],
                     "qty_estimee": d["qty"], "prix_reference": round(self.s.market.price(sym) or 0, 2),
                     "these": these[:1500], "statut": "en_attente",
                     "cree_le": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
                self.s.add_plan(o)
                self.orders.append({**record, **o, "resultat": "planifié pour l'ouverture"})
                return {"planifie": True, "message": f"Vente de {d['qty']} {sym} planifiée pour l'ouverture."}
            r = self.s.broker.sell(self.a.id, sym, d["qty"], these)
            self.orders.append({**record, **d, "resultat": r["message"], "ok": r["ok"]})
            return r
        return {"refuse": "action inconnue : acheter ou vendre"}

    def t_annuler_ordre(self, symbole=""):
        sym = clean_symbol(symbole)
        n = self.s.cancel_plan(self.a.id, sym)
        return {"ok": bool(n), "message": f"{n} ordre(s) planifié(s) annulé(s) sur {sym}" if n else "aucun ordre planifié sur ce titre"}

    def t_ajuster_stop(self, symbole="", nouveau_stop=None):
        sym = clean_symbol(symbole)
        val = self.valuation()
        ok, msg, d = check_stop(self.s.cfg, val, sym, nouveau_stop, self.s.market.price(sym))
        if not ok:
            self.log("refus", symbole=sym, raison=msg)
            return {"refuse": msg}
        r = self.s.broker.adjust_stop(self.a.id, sym, d["stop"])
        self.orders.append({"action": "ajuster_stop", "symbole": sym, "stop": d["stop"], "resultat": r["message"],
                            "ok": r["ok"]})
        return r

    def t_terminer_session(self, compte_rendu=""):
        self.done = True
        self.compte_rendu = compte_rendu.strip()
        return {"ok": True, "message": "Séance terminée. À la prochaine séance !"}
