"""L'équipe de 6 IA et le déroulé d'une séance.

Chaque IA a les mêmes fonctions que les IA d'Aywen : elle choisit seule ses outils (actualité,
screener, données boursières, navigateur web, réseaux, notes…), lit ses skills, garde ses notes
comme mémoire et son contexte est remis à zéro à chaque séance. Mais au lieu de se faire
concurrence, les 6 travaillent ENSEMBLE sur un seul compte :
  1. 4 analystes (stratégies différentes) cherchent en parallèle et PROPOSENT des ordres ;
  2. le critique contrôle chaque proposition avec les outils ;
  3. le gérant (stratégie Qualité) décide et PASSE les ordres, puis tient le journal de l'équipe.

Trois moments par jour de bourse :
  - 9 h (Paris)        PRÉPARATION : bourse de New York fermée, les ordres sont planifiés ;
  - 15 h 30            OUVERTURE   : le programme exécute les ordres planifiés au prix d'ouverture ;
  - fin d'après-midi   SUIVI       : bourse ouverte, l'équipe fait le point et agit en direct.
"""
import concurrent.futures as cf
import datetime as dt
import json
import logging
import os
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo

from . import classement, memory, notify, tools
from .agent_tools import SKILL_INFO, AgentEnv, Market, declarations
from .comptes import Comptes
from .executor import Broker
from .llm import ContextTooLarge, LLMError
from .risk import check_buy, check_sell, trailing_stop

log = logging.getLogger("seance")
SKILLS = Path(__file__).resolve().parent.parent / "skills"
PARIS, NY = ZoneInfo("Europe/Paris"), ZoneInfo("America/New_York")
AGENT_DEADLINE_S = 20 * 60
GROQ_REQUEST_CHARS = 21_000  # ~6 300 tokens : taille visée d'une requête Groq (consignes + outils + conversation)
ACCOUNT = "equipe"  # le compte unique de l'équipe (tout le compte Alpaca paper)


@dataclass
class Agent:
    id: str
    nom: str
    role: str  # analyste | critique | gerant
    provider: str
    key_index: int
    models: list[str] = field(default_factory=list)
    strategie: str = ""
    inspire_de: str = ""


GEMINI = ["gemini-3.5-flash", "gemini-3.7-flash", "gemini-3.5-flash-lite"]
AGENTS = [
    Agent("qualite", "Analyste Qualité", "analyste", "gemini", 0, GEMINI, "qualite", "Claude"),
    Agent("equilibre", "Analyste Équilibre", "analyste", "gemini", 1, GEMINI, "equilibre", "ChatGPT"),
    Agent("sentiment", "Analyste Sentiment", "analyste", "groq", 0,
          ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"], "sentiment", "Grok"),
    Agent("contrarien", "Analyste Contrarien", "analyste", "groq", 1,
          ["qwen/qwen3.8-27b", "openai/gpt-oss-20b", "openai/gpt-oss-120b"], "contrarien", "Mistral"),
    Agent("critique", "Critique", "critique", "groq", 2,
          ["openai/gpt-oss-20b", "qwen/qwen3.8-27b", "openai/gpt-oss-120b"], "critique", ""),
    Agent("gerant", "Gérant", "gerant", "gemini", 2, GEMINI, "gerant", "Claude"),
]
ANALYSTES = [a for a in AGENTS if a.role == "analyste"]
CRITIQUE = next(a for a in AGENTS if a.role == "critique")
GERANT = next(a for a in AGENTS if a.role == "gerant")
# Repères du résumé du marché (fonds cotés suivis gratuitement chez Alpaca)
BRIEF_INDICES = [("SPY", "S&P 500"), ("QQQ", "Nasdaq 100"), ("IWM", "petites capitalisations"), ("DIA", "Dow Jones")]
BRIEF_MACRO = [("TLT", "obligations US à 20 ans"), ("GLD", "or"), ("USO", "pétrole"), ("UUP", "dollar")]
BRIEF_SECTEURS = [("XLK", "technologie"), ("XLC", "communication"), ("XLY", "consommation cyclique"),
                  ("XLP", "consommation de base"), ("XLF", "finance"), ("XLV", "santé"), ("XLI", "industrie"),
                  ("XLE", "énergie"), ("XLB", "matériaux"), ("XLU", "services publics"), ("XLRE", "immobilier")]
ANALYST_NOTE = re.compile(r"\b(Maintains|Reiterates|Upgrades|Downgrades|Initiates|Assumes|Price Target)\b", re.I)
MODES = {
    "preparation": "Préparation (bourse fermée, ordres planifiés pour l'ouverture)",
    "ouverture": "Ouverture (exécution des ordres planifiés)",
    "suivi": "Suivi (bourse ouverte, ordres immédiats)",
}
ROLES = {
    "analyste": ("Tu es l'un des 4 ANALYSTES de l'équipe. Tu ne passes pas d'ordre : tu cherches des idées selon "
                 "TA stratégie et tu les soumets avec proposer_ordre (3 au maximum, thèse complète). Le critique les "
                 "contrôlera, puis le gérant décidera. Ne proposer aucune idée est valable si rien ne le justifie. "
                 "Vérifie aussi les positions actuelles du compte : propose de vendre si la thèse est cassée."),
    "critique": ("Tu es le CRITIQUE de l'équipe (avocat du diable). Tu ne passes pas d'ordre et tu ne proposes rien : "
                 "pour chaque proposition des analystes, vérifie les faits avec tes outils si nécessaire, puis donne "
                 "ton verdict avec donner_avis (ok, reserve ou rejet, avec la raison)."),
    "gerant": ("Tu es le GÉRANT de l'équipe : c'est toi qui décides et qui passes les ordres sur le compte avec "
               "passer_ordre. Tu reçois les propositions des analystes et les avis du critique ; tu peux vérifier "
               "toi-même avec les outils. Tes notes sont le journal de bord de l'équipe."),
}


def _skill(name: str) -> str:
    return (SKILLS / "commun" / f"{name}.md").read_text(encoding="utf-8")


def _strategy(name: str) -> str:
    return (SKILLS / "strategies" / f"{name}.md").read_text(encoding="utf-8")


def _dumps(x) -> str:
    return json.dumps(x, ensure_ascii=False, separators=(",", ":"), default=str)


def compact(messages: list[dict], budget: int, keep_last: int = 3) -> None:
    """Raccourcit les anciens résultats d'outils quand la conversation devient trop longue
    (les clés gratuites limitent le nombre de tokens par minute)."""
    def size():
        return sum(len(m.get("text") or m.get("content") or "") + len(json.dumps(m.get("calls") or []))
                   for m in messages)
    tool_idx = [i for i, m in enumerate(messages) if m["role"] == "tool"]
    for i in tool_idx[:-keep_last] if keep_last else tool_idx:
        if size() <= budget:
            return
        c = messages[i]["content"]
        if len(c) > 240:
            messages[i]["content"] = c[:200] + "… [ancien résultat raccourci]"
    # Encore trop long : les résultats récents sont résumés à leur début, sauf le tout dernier.
    for i in tool_idx[-keep_last:-1] if keep_last > 1 else []:
        if size() <= budget:
            return
        c = messages[i]["content"]
        if len(c) > 1600:
            messages[i]["content"] = c[:1500] + "… [résultat raccourci]"


class Session:
    def __init__(self, cfg, alpaca, router, mode: str, dry_run: bool, offline: bool = False, complet: bool = False):
        self.cfg, self.alpaca, self.router = cfg, alpaca, router
        self.mode, self.dry_run, self.offline = mode, dry_run, offline
        self.complet = complet  # séance lancée à la main : toute l'équipe, même en suivi calme
        self.account = ACCOUNT
        self.now = dt.datetime.now(dt.timezone.utc)
        self.when = self.now.astimezone(PARIS).strftime("%Y-%m-%d %H:%M (Paris)")
        self.plan: dict = {}
        self.lock = threading.Lock()
        self.new_notes: dict = {}
        self.results: dict = {}
        self.executions: list = []
        self.proposals: list = []
        self.avis: dict = {}
        self.rappels: list = memory.read_rappels()
        self.bilan = ""
        self.frein: str | None = None  # raison du frein d'urgence (aucun achat) s'il est actif
        self.ecarts: list = []  # différences entre le registre de l'équipe et les positions Alpaca
        self.lecons: list = memory.read_lecons()  # mémoire longue de l'équipe
        self.new_lecons: list = []
        self.brief = ""  # résumé du marché préparé par le programme, donné aux 6 IA
        self.track: dict = {}  # bilan des idées des analystes (bot/classement.py)
        self.stops_suiveurs: list = []
        self.allegee: str | None = None  # séance de suivi allégée (le gérant seul) et pourquoi
        self.suivi_raisons: list = []

    # ------------------------------------------------------------------ données partagées de la séance
    def add_plan(self, order: dict):
        with self.lock:
            self.plan.setdefault("ordres", []).append(order)

    def cancel_plan(self, acct, sym) -> int:
        with self.lock:
            n = 0
            for o in self.plan.get("ordres", []):
                if o.get("compte") == acct and o["symbole"] == sym and o["statut"] == "en_attente":
                    o["statut"], o["resultat"] = "annule", "annulé par le gérant"
                    n += 1
            return n

    def add_proposal(self, p: dict):
        with self.lock:
            self.proposals.append(p)

    def set_avis(self, v: dict):
        with self.lock:
            self.avis[v["id"]] = v

    def add_lecon(self, l: dict):
        with self.lock:
            self.new_lecons.append(l)

    def buy_context(self, sym: str, val: dict, planned: list) -> dict:
        """Ce dont les garde-fous ont besoin pour un achat : frein d'urgence, secteur du titre (et ce qui
        est déjà investi ou planifié dans ce secteur) et nombre de jours avant ses résultats."""
        f = self.market.fundamentals(sym) or {}
        secteur = f.get("secteur")
        ctx = {"frein": self.frein, "secteur": secteur, "jours_resultats": f.get("jours_avant_resultats")}
        if secteur:
            def same(s):
                return (self.market.fundamentals(s) or {}).get("secteur") == secteur
            ctx["secteur_valeur"] = (sum(p["valeur"] for p in val["positions"] if same(p["symbole"]))
                                     + sum(o.get("montant_usd") or 0 for o in planned
                                           if o["action"] == "acheter" and same(o["symbole"])))
        return ctx

    def check_ledger(self):
        """Compare le registre de l'équipe aux positions réelles chez Alpaca et signale les écarts."""
        try:
            real = {p["symbol"]: int(float(p["qty"])) for p in self.alpaca.positions()}
        except Exception as e:
            log.warning("contrôle du registre impossible : %s", e)
            return
        self.ecarts = self.comptes.reconcile(real)
        if self.ecarts:
            texte = "; ".join(self.ecarts)
            log.warning("Écarts registre / Alpaca : %s", texte)
            self.comptes.event(ACCOUNT, f"Écart entre le registre et Alpaca : {texte}")
            if not self.dry_run:
                notify.send("Écart avec Alpaca", texte[:900], tags="warning")

    def emergency_brake(self, equity: float, last_equity: float) -> str | None:
        """Frein d'urgence : plus aucun achat si le compte chute trop vite (les ventes restent possibles)."""
        cfg = self.cfg
        if last_equity > 0 and (day := (equity / last_equity - 1) * 100) <= -cfg.frein_jour_pct:
            return f"le compte a perdu {-day:.1f} % depuis la clôture précédente (seuil {cfg.frein_jour_pct:g} %)"
        try:  # valeur du compte 5 séances plus tôt
            eq = [v for v in (self.alpaca.portfolio_history("1M", "1D").get("equity") or []) if v]
        except Exception:
            eq = []
        if len(eq) >= 6 and (week := (equity / eq[-6] - 1) * 100) <= -cfg.frein_semaine_pct:
            return f"le compte a perdu {-week:.1f} % en une semaine (seuil {cfg.frein_semaine_pct:g} %)"
        return None

    def apply_trailing_stops(self):
        """Stop suiveur codé (pas une décision d'IA) : remonte le stop des positions en gain."""
        val = self.comptes.valuation(ACCOUNT, self.market.prices(self.comptes.symbols()))
        for p in val["positions"]:
            new = trailing_stop(self.cfg, p)
            if new is None:
                continue
            r = self.broker.adjust_stop(ACCOUNT, p["symbole"], new, source="stop suiveur")
            texte = (f"Stop suiveur sur {p['symbole']} : {p['stop'] or 0:.2f} $ → {new:.2f} $ "
                     f"(cours {p['prix']:.2f} $, achat {p['prix_achat']:.2f} $)")
            self.stops_suiveurs.append({"symbole": p["symbole"], "ancien": p["stop"], "nouveau": new,
                                        "ok": r["ok"], "message": r["message"]})
            if not r["ok"]:
                log.warning("stop suiveur %s : %s", p["symbole"], r["message"])
                continue
            log.info(texte)
            self.comptes.event(ACCOUNT, texte)
            if not self.dry_run and (p["stop"] or 0) < p["prix_achat"] <= new:
                notify.send(f"{p['symbole']} protégée", f"{texte}. Cette position ne peut plus perdre d'argent.",
                            tags="shield")

    def _moves(self, sym: str) -> dict | None:
        """Variation d'un titre depuis la dernière clôture, sur 5 et sur 21 séances."""
        bars = self.market.bars([sym]).get(sym) or []
        today = self.now.astimezone(NY).date().isoformat()
        past = [b for b in bars if str(b.get("t", ""))[:10] < today]
        if len(past) < 22:
            return None
        live = self.market.price(sym) or past[-1]["c"]
        k = 0 if self.market_open else 1  # bourse fermée : la dernière clôture est la séance du jour
        return {"jour": (live / past[-1]["c"] - 1) * 100, "semaine": (live / past[-5 - k]["c"] - 1) * 100,
                "mois": (live / past[-21 - k]["c"] - 1) * 100}

    def track_record(self) -> dict:
        """Ce qu'ont rapporté les idées passées de chaque analyste : chacun apprend de ses résultats."""
        try:
            props = classement.load_propositions()
            prices = self.market.prices(sorted({p["symbole"] for p in props})) if props else {}
            return classement.compute(props, prices, [a.id for a in ANALYSTES])
        except Exception as e:  # un bilan manquant ne doit pas bloquer la séance
            log.warning("bilan des analystes indisponible : %s", e)
            return {}

    def market_breadth(self) -> str:
        """Combien des grandes valeurs de l'univers montent vraiment : une hausse portée par quelques géants
        est plus fragile qu'une hausse générale. Calculé avec les cours déjà téléchargés pour le screener."""
        n = above50 = above200 = highs = lows = 0
        for bars in self.market.universe().values():
            closes = [b["c"] for b in bars]
            if len(closes) < 200:
                continue
            last, year = closes[-1], closes[-252:]
            n += 1
            above50 += last > sum(closes[-50:]) / 50
            above200 += last > sum(closes[-200:]) / 200
            highs += last >= max(year) * 0.98
            lows += last <= min(year) * 1.02
        if n < 50:
            return ""
        return (f"sur {n} grandes valeurs, {above50 * 100 // n} % sont au-dessus de leur moyenne 50 jours et "
                f"{above200 * 100 // n} % au-dessus de leur moyenne 200 jours ; {highs} sont à moins de 2 % de leur "
                f"plus haut sur un an, {lows} à moins de 2 % de leur plus bas")

    def market_brief(self) -> str:
        """Résumé du marché préparé par le programme et donné aux 6 IA : indices, taux et matières premières,
        secteurs, positions du compte et grands titres. Il leur évite de dépenser des appels d'outils."""
        try:
            self.market.bars([s for s, _ in BRIEF_INDICES + BRIEF_MACRO + BRIEF_SECTEURS])
            fmt = lambda v: f"{v:+.1f} %".replace(".", ",")  # noqa: E731

            def line(items):
                out = []
                for sym, name in items:
                    m = self._moves(sym)
                    if m:
                        out.append(f"{name} ({sym}) {fmt(m['jour'])} · 5 séances {fmt(m['semaine'])} · 1 mois {fmt(m['mois'])}")
                return " ; ".join(out)

            L = []
            if idx := line(BRIEF_INDICES):
                L.append(f"- Indices : {idx}")
            if mac := line(BRIEF_MACRO):
                L.append(f"- Taux, matières premières et dollar : {mac}")
            if breadth := self.market_breadth():
                L.append(f"- Largeur du marché : {breadth}")
            sect = [(name, sym, m["semaine"]) for sym, name in BRIEF_SECTEURS if (m := self._moves(sym))]
            if sect:
                sect.sort(key=lambda x: x[2], reverse=True)
                top = ", ".join(f"{n} ({s}) {fmt(v)}" for n, s, v in sect[:3])
                bottom = ", ".join(f"{n} ({s}) {fmt(v)}" for n, s, v in sect[-3:][::-1])
                L.append(f"- Secteurs sur 5 séances : les plus forts {top} ; les plus faibles {bottom}")
            val = self.comptes.valuation(ACCOUNT, self.market.prices(self.comptes.symbols()))
            pos = []
            for p in val["positions"]:
                m = self._moves(p["symbole"])
                stop = f", stop à {(1 - p['stop'] / p['prix']) * 100:.1f} % sous le cours".replace(".", ",") if p.get("stop") and p["prix"] else ""
                jour = f"{fmt(m['jour'])} aujourd'hui, " if m else ""
                pos.append(f"{p['symbole']} {jour}{fmt(p['pl_pct'])} depuis l'achat{stop}")
            L.append("- Positions du compte : " + ("; ".join(pos) if pos else "aucune"))
            heads = []
            if not self.offline:
                try:  # la une Économie de Google Actualités
                    heads += [(n["date"][5:], n["source"], n["titre"]) for n in tools.google_news_top(5)]
                except Exception as e:
                    log.info("une de Google Actualités indisponible : %s", e)
            try:  # le fil Benzinga d'Alpaca, sans les simples changements de note des analystes
                news = [n for n in self.alpaca.news(None, limit=50) if not ANALYST_NOTE.search(n.get("headline") or "")]
            except Exception:
                news = []
            heads += [(str(n.get("created_at", ""))[5:16].replace("T", " "), n.get("source", ""), n.get("headline") or "")
                      for n in news[:4]]
            if heads:
                L.append("- Grands titres de l'actualité financière (heure UTC) :")
                L += [f"  - {when} · {src} · {title[:150]}" for when, src, title in heads]
            if not L:
                return ""
            return ("RÉSUMÉ DU MARCHÉ (préparé par le programme au début de la séance ; variations depuis la dernière "
                    "clôture, sur 5 et sur 21 séances) :\n" + "\n".join(L) + "\n\n")
        except Exception as e:  # le résumé est un plus : il ne doit jamais bloquer la séance
            log.warning("résumé du marché indisponible : %s", e)
            return ""

    def suivi_reasons(self) -> list[str]:
        """Ce qui justifie de réveiller toute l'équipe en séance de suivi. Sans raison, la séance est allégée :
        le gérant seul vérifie les positions, ce qui économise les quotas gratuits des IA."""
        cfg = self.cfg
        if cfg.suivi_complet or self.complet:
            return ["séance complète demandée"]
        out = []
        due = [r for r in self.rappels if r["statut"] == "actif" and r["date"] <= self.trading_date
               and r["seance"] in ("toutes", "suivi")]
        if due:
            out.append(f"{len(due)} rappel(s) à traiter aujourd'hui")
        events = self.comptes.take_events(ACCOUNT, self.comptes.agent(ACCOUNT).get("derniere_seance"))
        hits = [e for e in events if any(k in e for k in ("Stop loss déclenché", "Objectif de gain atteint",
                                                          "non exécuté", "Écart entre le registre"))]
        if hits:
            out.append("événement sur le compte : " + " ; ".join(hits)[:200])
        spy = self._moves("SPY")
        if spy and abs(spy["jour"]) >= cfg.suivi_marche_pct:
            out.append(f"S&P 500 {spy['jour']:+.1f} % aujourd'hui")
        val = self.comptes.valuation(ACCOUNT, self.market.prices(self.comptes.symbols()))
        for p in val["positions"]:
            m = self._moves(p["symbole"])
            if m and abs(m["jour"]) >= cfg.suivi_mouvement_pct:
                out.append(f"{p['symbole']} {m['jour']:+.1f} % aujourd'hui")
            if p.get("stop") and p["prix"] and (p["prix"] / p["stop"] - 1) * 100 <= 2:
                out.append(f"{p['symbole']} à moins de 2 % de son stop")
        return out

    # ------------------------------------------------------------------ séance
    def run(self) -> dict:
        memory.state_start(self.mode, self.dry_run, [a.id for a in AGENTS])
        try:
            clock = self.alpaca.clock()
            self.market_open = bool(clock.get("is_open"))
            nxt = clock.get("next_open")
            self.trading_date = (self.now.astimezone(NY).date().isoformat() if self.market_open or not nxt
                                 else dt.datetime.fromisoformat(nxt.replace("Z", "+00:00")).astimezone(NY).date().isoformat())
            account = self.alpaca.account()
            equity = float(account["equity"])
            self.comptes = Comptes.load([ACCOUNT], equity, persist=not self.dry_run)
            self.comptes.sync(self.alpaca)
            if not self.offline:
                self.check_ledger()
            self.frein = self.emergency_brake(equity, float(account.get("last_equity") or 0))
            if self.frein:
                log.warning("Frein d'urgence : %s", self.frein)
                self.comptes.event(ACCOUNT, f"Frein d'urgence actif : {self.frein}")
                if not self.dry_run:
                    notify.send("Frein d'urgence", f"Aucun achat pendant cette séance : {self.frein}.",
                                tags="rotating_light", priorite="high")
            self.broker = Broker(self.alpaca, self.comptes, self.dry_run)
            self.market = Market(self.alpaca, self.offline, self.now.astimezone(NY).date())
            self.journal = memory.recent_journal(10)
            self.before = self.comptes.valuation(ACCOUNT, {})
            limit = (dt.date.fromisoformat(self.trading_date) - dt.timedelta(days=3)).isoformat()
            for r in self.rappels:  # un rappel non traité 3 jours après sa date expire
                if r["statut"] == "actif" and r["date"] < limit:
                    r["statut"] = "expire"
            if self.market_open:  # cours de la séance régulière uniquement
                self.apply_trailing_stops()

            if self.mode == "ouverture":
                self.plan = memory.read_plan(simulation=self.offline)
                self.execute_plan()
            else:
                if self.mode == "preparation":
                    self.plan = {"date": self.trading_date, "cree_le": self.now.isoformat(timespec="seconds"),
                                 "simulation": self.dry_run, "ordres": []}
                self.brief = self.market_brief()
                self.track = self.track_record()
                if self.mode == "suivi":
                    self.suivi_raisons = self.suivi_reasons()
                    if not self.suivi_raisons:
                        self.allegee = ("rien de notable depuis ce matin : pas de rappel du jour, pas d'événement sur "
                                        "le compte, marché et positions calmes")
                        log.info("Séance de suivi allégée : %s", self.allegee)
                if self.allegee:
                    for a in ANALYSTES + [CRITIQUE]:
                        memory.state_agent(a.id, statut="termine", action="séance allégée : pas sollicité")
                else:
                    # 1. les analystes cherchent en parallèle
                    with cf.ThreadPoolExecutor(max_workers=len(ANALYSTES)) as pool:
                        for a, res in zip(ANALYSTES, pool.map(self.run_agent, ANALYSTES)):
                            self.results[a.id] = res
                    # 2. le critique contrôle les propositions
                    if self.proposals:
                        self.results[CRITIQUE.id] = self.run_agent(CRITIQUE)
                    else:
                        memory.state_agent(CRITIQUE.id, statut="termine", action="aucune proposition à contrôler")
                # 3. le gérant décide
                self.results[GERANT.id] = self.run_agent(GERANT)
                # 4. le vendredi soir, le gérant écrit le bilan de la semaine
                if self.mode == "suivi" and (self.now.astimezone(PARIS).weekday() == 4 or os.getenv("BILAN_FORCE")):
                    self.bilan = self.weekly_review()
            self.auto_reminders()
            self.finish()
            return self.results
        finally:
            memory.state_stop()

    # ------------------------------------------------------------------ une IA
    def max_steps(self, a: Agent) -> int:
        c = self.cfg
        if a.role == "analyste":
            return c.max_steps_analyste if self.mode == "preparation" else c.max_steps_analyste_suivi
        if a.role == "critique":  # chaque avis compte comme un appel : un de plus par proposition
            return c.max_steps_critique + len(self.proposals)
        return c.max_steps_gerant_leger if self.allegee else c.max_steps_gerant

    def system_prompt(self, a: Agent) -> str:
        cfg = self.cfg
        paris = self.now.astimezone(PARIS).strftime("%A %d/%m/%Y %H:%M")
        ny = self.now.astimezone(NY).strftime("%H:%M")
        if self.market_open:
            moment = ("SÉANCE DE SUIVI : la bourse de New York est OUVERTE, les ordres du gérant sont exécutés "
                      "immédiatement. On fait le point sur les positions (thèse, stop, catalyseurs) et on agit si c'est justifié.")
        else:
            moment = ("SÉANCE DE PRÉPARATION : la bourse de New York est FERMÉE (ouverture à 15h30, heure de Paris). "
                      "C'est MAINTENANT que l'équipe décide de ce qui sera acheté ou vendu à l'ouverture : les ordres du "
                      "gérant sont PLANIFIÉS puis exécutés automatiquement au prix d'ouverture (annulés si le cours "
                      f"s'écarte de plus de {cfg.max_gap_pct:g} % du prix de ce matin). La séance suivante n'aura lieu "
                      "qu'en fin d'après-midi.")
        # Groq gratuit accepte des requêtes plus courtes : la liste des fiches sans leur description
        skills = (", ".join(SKILL_INFO) if a.provider == "groq"
                  else "\n".join(f"- {k} : {v}" for k, v in SKILL_INFO.items()))
        return (
            f"Tu es « {a.nom} », l'une des 6 IA d'une équipe qui gère ensemble UN compte d'actions cotées aux "
            "États-Unis (paper trading chez Alpaca, argent virtuel). L'équipe : 4 analystes aux stratégies différentes "
            "(Qualité, Équilibre, Sentiment, Contrarien), un critique et un gérant.\n"
            f"{ROLES[a.role]}\n"
            f"Nous sommes le {paris} à Paris ({ny} à New York).\n{moment}\n\n"
            "Tu travailles avec tes outils : c'est toi qui décides lesquels utiliser et dans quel ordre. Tes notes "
            "sont ta seule mémoire entre deux séances. Termine TOUJOURS par terminer_session.\n"
            f"Tu disposes d'environ {self.max_steps(a)} appels d'outils : analyse en profondeur peu d'idées et garde "
            "de quoi conclure.\n\n"
            f"{_skill('00-lisez-moi')}\n{_skill('routine-de-session')}\n{_strategy(a.strategie)}\n\n"
            f"SKILLS DISPONIBLES (outil lire_skill) :\n{skills}\n\n"
            f"LIMITES APPLIQUÉES PAR LE CODE : {cfg.max_position_pct:g} % max du compte par titre ; "
            f"{cfg.min_cash_pct:g} % de liquidités gardées ; {cfg.max_positions} positions max ; {cfg.max_orders} ordres "
            f"max par séance ; stop loss obligatoire entre {cfg.min_stop_distance_pct:g} et {cfg.max_stop_distance_pct:g} % ; "
            f"objectif de gain ≥ {cfg.min_reward_risk:g} × le stop ; pas d'action sous {cfg.min_price:g} $ ; un stop ne "
            f"se descend jamais ; pas de rachat d'un titre vendu il y a moins de {cfg.anti_churn_days} jours ; "
            + (f"stop suiveur automatique (le code s'en charge) : à +{cfg.stop_suiveur_pct:g} % le stop remonte au prix "
               f"d'achat, à +{2 * cfg.stop_suiveur_pct:g} % il suit le cours à {cfg.stop_suiveur_distance_pct:g} % en "
               "dessous ; " if cfg.stop_suiveur_pct > 0 else "")
            + f"{cfg.max_sector_pct:g} % max du compte dans un même secteur ; pas d'achat d'un titre qui publie ses "
            f"résultats dans {cfg.earnings_blackout_days} jour(s) ou moins ; frein d'urgence (plus aucun achat) si le "
            f"compte perd {cfg.frein_jour_pct:g} % en un jour ou {cfg.frein_semaine_pct:g} % en une semaine ; "
            f"{cfg.max_web_searches} recherches web par IA et par séance. Réponds en français."
            + (f"\n\nFREIN D'URGENCE ACTIF : {self.frein}. Aucun achat n'est possible pendant cette séance : "
               "concentre-toi sur la protection du compte (thèses cassées, stops, ventes)." if self.frein else "")
        )

    def opening(self, a: Agent) -> str:
        notes = memory.read_notes(a.id) or "(aucune note : c'est ta toute première séance)"
        txt = f"Nouvelle séance : {MODES[self.mode]}.\n\nTES NOTES (écrites lors de ta dernière séance) :\n{notes}\n\n"
        txt += self.brief
        txt += classement.summary(a.role, a.id, self.track, {x.id: x.nom.replace("Analyste ", "") for x in ANALYSTES})
        if self.lecons:
            txt += ("LEÇONS APPRISES PAR L'ÉQUIPE (mémoire longue, à respecter) :\n"
                    + "\n".join(f"- {l['texte']}" for l in self.lecons[-15:]) + "\n\n")
        txt += self.reminders_text()
        if a.role == "gerant":
            acct = self.comptes.agent(ACCOUNT)
            events = self.comptes.take_events(ACCOUNT, acct.get("derniere_seance"))
            txt += ("CE QUI S'EST PASSÉ SUR LE COMPTE DEPUIS LA DERNIÈRE SÉANCE :\n"
                    + ("\n".join(f"- {e}" for e in events) or "- rien de particulier") + "\n\n")
            if self.allegee:
                return txt + (f"SÉANCE DE SUIVI ALLÉGÉE ({self.allegee}) : les analystes et le critique ne sont pas "
                              "sollicités, pour économiser les quotas des IA. Vérifie les positions (thèse, actualité, "
                              "stop) avec tes outils et agis si c'est justifié ; tu peux aussi saisir une occasion "
                              "évidente. Mets à jour le journal de bord de l'équipe avec ecrire_notes, puis termine.")
            txt += (f"PROPOSITIONS DES ANALYSTES :\n{_dumps(self.proposals) if self.proposals else 'aucune'}\n\n"
                    f"AVIS DU CRITIQUE :\n{_dumps(list(self.avis.values())) if self.avis else 'aucun'}\n\n"
                    f"COMPTES RENDUS DES ANALYSTES :\n"
                    + "\n".join(f"- {self.results[x.id]['nom']} : {self.results[x.id]['compte_rendu'][:500]}"
                                for x in ANALYSTES if x.id in self.results) + "\n\n"
                    "Décide des ordres de cette séance (en indiquant la proposition retenue dans « source »), "
                    "mets à jour le journal de bord de l'équipe avec ecrire_notes, puis termine.")
        elif a.role == "critique":
            txt += (f"PROPOSITIONS À CONTRÔLER :\n{_dumps(self.proposals)}\n\n"
                    "Donne un avis (donner_avis) sur CHAQUE proposition, puis termine.")
        else:
            txt += "Applique ta routine de séance avec tes outils."
        return txt

    def reminders_text(self) -> str:
        """Rappels de l'équipe : ceux du jour (à traiter) et ceux des 7 prochains jours."""
        today = self.trading_date
        soon = (dt.date.fromisoformat(today) + dt.timedelta(days=7)).isoformat()
        actifs = [r for r in self.rappels if r["statut"] == "actif"]
        due = [r for r in actifs if r["date"] <= today and r["seance"] in ("toutes", self.mode)]
        nxt = [r for r in actifs if today < r["date"] <= soon]

        def line(r):
            sym = f"{r['symbole']} : " if r["symbole"] else ""
            det = f" — {r['details']}" if r["details"] else ""
            return f"- [{r['id']}] {r['date']} {sym}{r['titre']}{det} (créé par {r['cree_par']})"

        out = ""
        if due:
            out += ("RAPPELS DU JOUR (à traiter maintenant : vérifie l'événement, agis en fonction, puis "
                    "terminer_rappel) :\n" + "\n".join(line(r) for r in due) + "\n\n")
        if nxt:
            out += "RAPPELS DES 7 PROCHAINS JOURS :\n" + "\n".join(line(r) for r in nxt) + "\n\n"
        return out

    def _missing(self, a: Agent) -> str:
        if a.role != "critique":
            return ""
        missing = [p["id"] for p in self.proposals if p["id"] not in self.avis]
        return f" Propositions encore sans avis : {', '.join(missing)}." if missing else ""

    def run_agent(self, a: Agent) -> dict:
        env = AgentEnv(self, a)
        start = time.time()
        system = self.system_prompt(a)
        tools = declarations(a.role, self.market_open)
        messages = [{"role": "user", "text": self.opening(a)}]
        env.log("notes", texte="Relit ses notes" + (", les propositions et les avis" if a.role == "gerant" else ""))
        max_steps = self.max_steps(a)
        if a.provider == "groq":  # Groq gratuit refuse les requêtes de plus de ~7 000 tokens : on garde de la marge
            fixed = len(system) + len(json.dumps(tools, ensure_ascii=False))
            budget = max(5000, min(14000, GROQ_REQUEST_CHARS - fixed))
        else:
            budget = 60000
        keep = {"passer_ordre", "annuler_ordre", "ajuster_stop", "proposer_ordre", "donner_avis",
                "ecrire_notes", "noter_lecon", "terminer_session"}
        final_tools = [t for t in tools if t["name"] in keep]  # en fin de séance : agir et conclure
        nudged, reminded, final, final_turns, error, used = False, False, False, 0, None, ""
        while not env.done:
            if time.time() - start > AGENT_DEADLINE_S:
                error = "temps maximum de séance dépassé"
                break
            if not reminded and max_steps > 4 and env.tool_calls >= max_steps - 3:
                reminded = True
                messages.append({"role": "user", "text": "Il te reste environ 3 appels d'outils : conclus, agis si "
                                                         "c'est justifié, écris tes notes et termine." + self._missing(a)})
            if not final and env.tool_calls >= max_steps:
                final = True
                messages.append({"role": "user", "text": "Tu as utilisé tous tes appels de recherche : tu peux "
                                                         "encore agir, mettre à jour tes notes, puis appelle "
                                                         "terminer_session." + self._missing(a)})
            if final:
                if final_turns >= 3:
                    break
                final_turns += 1
            now_tools = final_tools if final else tools
            compact(messages, budget)
            memory.state_agent(a.id, statut="reflechit")
            try:
                msg, used = self.router.chat(a, system, messages, now_tools, label=a.id)
            except ContextTooLarge:
                compact(messages, budget // 3, keep_last=1)
                try:
                    msg, used = self.router.chat(a, system, messages, now_tools, label=a.id)
                except LLMError as e:
                    error = str(e)
                    break
            except LLMError as e:
                error = str(e)
                break
            messages.append(msg)
            if msg.get("text"):
                env.log("pensee", texte=msg["text"][:2000])
            if not msg.get("calls"):
                if nudged:
                    env.compte_rendu = env.compte_rendu or msg.get("text", "")
                    break
                nudged = True
                messages.append({"role": "user", "text": "Continue avec tes outils, puis appelle terminer_session "
                                                         "avec ton compte rendu."})
                continue
            for c in msg["calls"]:
                messages.append({"role": "tool", "id": c["id"], "name": c["name"],
                                 "content": env.run(c["name"], c.get("args") or {})})
        if not env.done and not env.compte_rendu:
            env.compte_rendu = "(séance interrompue avant le compte rendu)"
        memory.state_agent(a.id, statut="termine" if not error else "erreur", action=(error or "")[:120])
        log.info("%s : %d outils, %d propositions, %d avis, %d ordres, %s", a.id, env.tool_calls,
                 len(env.proposals), len(env.avis), len(env.orders), error or "ok")
        return {"nom": a.nom, "role": a.role, "modele": used, "etapes": env.steps, "compte_rendu": env.compte_rendu,
                "propositions": env.proposals, "avis": env.avis, "ordres": env.orders, "erreur": error,
                "duree_s": round(time.time() - start), "outils": env.tool_calls}

    # ------------------------------------------------------------------ ouverture
    def execute_plan(self):
        cfg, plan = self.cfg, self.plan
        if not plan.get("ordres"):
            log.info("Aucun ordre planifié.")
            return
        todo = [o for o in plan["ordres"] if o["statut"] == "en_attente"]
        todo.sort(key=lambda o: 0 if o["action"] == "vendre" else 1)  # les ventes libèrent du cash
        for o in todo:
            acct, sym = o.get("compte", ACCOUNT), o["symbole"]
            price = self.market.price(sym)
            held = list(self.comptes.agent(acct)["positions"])
            val = self.comptes.valuation(acct, self.market.prices(held))
            if o["action"] == "acheter":
                ref = o.get("prix_reference") or price
                gap = (price / ref - 1) * 100 if price and ref else 0
                if not price:
                    o.update(statut="erreur", resultat="prix indisponible à l'ouverture")
                elif abs(gap) > cfg.max_gap_pct:
                    o.update(statut="annule", resultat=f"cours d'ouverture {price:.2f} $ trop éloigné du prix du matin "
                                                       f"{ref:.2f} $ ({gap:+.1f} %)")
                else:
                    ok, msg, d = check_buy(cfg, acct, val, sym, price, o["montant_usd"], o["stop_loss_pct"],
                                           o["take_profit_pct"], self.journal, clamp=True,
                                           **self.buy_context(sym, val, []))
                    if not ok:
                        o.update(statut="rejete", resultat=msg)
                    else:
                        r = self.broker.buy(acct, sym, d["qty"], d["stop_loss_pct"], d["take_profit_pct"],
                                            o.get("these", ""), source=o.get("source", ""))
                        o.update(statut="execute" if r["ok"] else "erreur", resultat=r["message"],
                                 prix_execution=r.get("prix"), qty=r.get("qty"))
            else:
                ok, msg, d = check_sell(cfg, acct, val, sym, o.get("pourcentage", 100), self.journal)
                if not ok:
                    o.update(statut="rejete", resultat=msg)
                else:
                    r = self.broker.sell(acct, sym, d["qty"], o.get("these", ""), source=o.get("source", ""))
                    o.update(statut="execute" if r["ok"] else "erreur", resultat=r["message"],
                             prix_execution=r.get("prix"), qty=r.get("qty"))
            o["traite_le"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
            self.comptes.event(acct, f"Ouverture, ordre planifié {o['action']} {sym} : {o['resultat']}")
            memory.state_agent(GERANT.id, statut="outil", action=f"ouverture : {o['action']} {sym} → {o['statut']}")
            log.info("Ouverture %s %s : %s", o["action"], sym, o["resultat"])
            self.executions.append(o)
        plan["execute_le"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

    # ------------------------------------------------------------------ fin de séance
    def auto_reminders(self):
        """Pour chaque action détenue, un rappel automatique à la date de ses prochains résultats."""
        today = dt.date.fromisoformat(self.trading_date)
        for sym in self.comptes.symbols():
            f = self.market.fundamentals(sym) or {}
            date = f.get("prochains_resultats")
            try:
                d = dt.date.fromisoformat(str(date))
            except ValueError:
                continue
            if not today <= d <= today + dt.timedelta(days=120):
                continue
            if any(r["symbole"] == sym and r["date"] == d.isoformat() and r["statut"] == "actif" for r in self.rappels):
                continue
            with self.lock:
                self.rappels.append({
                    "id": f"r{len(self.rappels) + 1}-{d.strftime('%m%d')}", "date": d.isoformat(),
                    "titre": f"Résultats de {sym}", "symbole": sym, "seance": "toutes", "cree_par": "systeme",
                    "details": "Publication des résultats d'une action détenue : réévaluer la thèse et le stop avant, "
                               "puis décider de garder, renforcer ou vendre selon les chiffres.",
                    "cree_le": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "statut": "actif"})

    def weekly_review(self) -> str:
        """Bilan de la semaine écrit par le gérant (ce qui a marché, ce qui a raté, les leçons)."""
        week = memory.recent_journal(7)
        execs = [e for e in week if e.get("type") == "execution" and e.get("statut") in ("exécuté", "envoyé")]
        hist = [h for h in memory.read_history() if h["date"] >= (self.now - dt.timedelta(days=7)).isoformat()]
        val = self.comptes.valuation(ACCOUNT, self.market.prices(self.comptes.symbols()))
        user = (f"C'est vendredi soir : écris le BILAN DE LA SEMAINE de l'équipe pour l'humain qui suit l'expérience.\n\n"
                f"VALEUR DU COMPTE : {_dumps(hist[-12:] or 'pas encore d historique')} ; maintenant {val['valeur']:.2f} $ "
                f"({val['pl_pct']:+.2f} % depuis le départ).\n\nPOSITIONS : {_dumps(val['positions'])}\n\n"
                f"ORDRES DE LA SEMAINE : {_dumps(execs[-40:]) if execs else 'aucun'}\n\n"
                f"JOURNAL DE BORD DE L'ÉQUIPE :\n{memory.read_notes(GERANT.id)[:2500]}\n\n"
                "Rédige en français, en 4 parties courtes : 1. Résultat de la semaine (chiffres) ; 2. Ce qui a marché ; "
                "3. Ce qui a raté ; 4. Leçons et plan pour la semaine prochaine. Factuel, pas plus de 250 mots, sans conseil "
                "d'investissement personnalisé. Termine par 1 à 3 lignes qui commencent par « LEÇON : », chacune une règle "
                "concrète et durable pour l'équipe : elles rejoindront la mémoire longue lue par les 6 IA.")
        try:
            msg, used = self.router.chat(GERANT, "Tu es le gérant d'une équipe d'IA qui gère un compte de paper trading.",
                                         [{"role": "user", "text": user}], [], label="bilan")
        except LLMError as e:
            log.warning("bilan de la semaine impossible : %s", e)
            return ""
        texte = (msg.get("text") or "").strip()
        for l in memory.lecons_du_bilan(texte):
            self.add_lecon({"date": self.trading_date, "auteur": "bilan", "texte": l})
        if texte and not self.dry_run:
            memory.write_bilan(self.now.astimezone(PARIS).strftime("%Y-%m-%d"), texte)
            notify.send("Bilan de la semaine", texte[:900], tags="memo")
        log.info("Bilan de la semaine écrit (%s)", used)
        return texte

    def finish(self):
        prices = self.market.prices(self.comptes.symbols())
        after = self.comptes.valuation(ACCOUNT, prices)
        if not self.dry_run:
            if self.mode != "ouverture":
                self.comptes.agent(ACCOUNT)["derniere_seance"] = self.now.isoformat(timespec="seconds")
            self.comptes.save()
            memory.append_history([{"date": self.now.isoformat(timespec="minutes"), "agent": ACCOUNT,
                                    "valeur": after["valeur"], "cash": after["cash"],
                                    "positions": len(after["positions"])}])
        if not self.dry_run:
            memory.write_rappels(self.rappels)
            memory.add_lecons(self.new_lecons)
            n = memory.archive_sessions()
            if n:
                log.info("%d ancienne(s) séance(s) rangée(s) dans memoire/archives/", n)
            planned = [o for o in self.plan.get("ordres", []) if o.get("statut") == "en_attente"]
            if self.mode == "preparation" and planned:
                lignes = [f"{o['action']} {o['symbole']}" + (f" pour {o.get('montant_usd', 0):.0f} $"
                                                               if o["action"] == "acheter" else "") for o in planned]
                notify.send(f"Plan du jour : {len(planned)} ordre(s)",
                            "\n".join(lignes) + "\nExécution à l'ouverture de New York.", tags="calendar")
        if self.mode in ("preparation", "ouverture") and self.plan:
            memory.write_plan(self.plan, simulation=self.dry_run)
        for p in self.proposals:  # chaque proposition garde son verdict et ce que le gérant en a fait
            p["avis"] = self.avis.get(p["id"])
            p["retenue"] = any(o.get("source") == p["id"] or (o.get("symbole"), o.get("action")) == (p["symbole"], p["action"])
                               for o in self.results.get(GERANT.id, {}).get("ordres", []))
        if not self.dry_run:
            memory.append_propositions([
                {"date": self.trading_date, "seance": self.mode, **{k: p.get(k) for k in (
                    "id", "auteur", "action", "symbole", "prix_ref", "montant", "stop_loss_pct", "take_profit_pct",
                    "confiance", "retenue")}, "verdict": (p.get("avis") or {}).get("verdict")} for p in self.proposals])
        name = self.now.astimezone(PARIS).strftime("%Y-%m-%d_%H%M") + f"_{self.mode}" + ("_simulation" if self.dry_run else "")
        data = {
            "nom": name, "quand": self.when, "ts": self.now.isoformat(), "mode": self.mode,
            "simulation": self.dry_run, "hors_ligne": self.offline, "marche_ouvert": self.market_open, "date_bourse": self.trading_date,
            "agents": {aid: {**r, "tokens": self.router.usage[aid]["tokens"], "appels": self.router.usage[aid]["appels"]}
                       for aid, r in self.results.items()},
            "propositions": self.proposals,
            "decision": (self.results.get(GERANT.id) or {}).get("compte_rendu", ""),
            "executions": self.executions,
            "plan": self.plan.get("ordres", []) if self.mode == "preparation" else [],
            "compte": after, "valeur_avant": self.before["valeur"],
            "cles": dict(self.router.slots),
            "bilan": self.bilan,
            "frein": self.frein,
            "lecons": self.new_lecons,
            "resume_marche": self.brief,
            "stops_suiveurs": self.stops_suiveurs,
            "allegee": self.allegee,
            "suivi_raisons": self.suivi_raisons,
            "ecarts": self.ecarts,
            "rappels": [r for r in self.rappels if r["statut"] == "actif" or r.get("fait_le", "") >= self.now.isoformat()],
        }
        memory.write_session_json(name, data)
        report = self.report(data)
        path = memory.write_report(name, report)
        summary = os.getenv("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a", encoding="utf-8") as f:
                f.write(report)
        log.info("Rapport : %s", path)

    def report(self, d) -> str:
        v = d["compte"]
        L = [f"# Séance du {d['quand']} : {MODES[self.mode]}", "",
             f"Compte paper Alpaca{' · SIMULATION (aucun ordre envoyé)' if self.dry_run else ''} · "
             f"valeur {v['valeur']:.2f} $ ({v['pl_pct']:+.2f} %) · liquidités {v['cash']:.2f} $ · "
             f"positions : {', '.join(p['symbole'] for p in v['positions']) or 'aucune'}", ""]
        if self.frein:
            L += [f"**Frein d'urgence actif** : {self.frein} (aucun achat).", ""]
        if self.allegee:
            L += [f"**Séance de suivi allégée** : {self.allegee}. Le gérant a vérifié seul les positions.", ""]
        if self.stops_suiveurs:
            L += ["**Stops suiveurs** : " + " ; ".join(f"{x['symbole']} {x['ancien'] or 0:.2f} → {x['nouveau']:.2f} $"
                                                     + ("" if x["ok"] else " (refusé)") for x in self.stops_suiveurs), ""]
        if self.ecarts:
            L += ["**Écarts entre le registre et Alpaca** : " + " ; ".join(self.ecarts), ""]
        if self.executions:
            L += ["## Ordres planifiés exécutés à l'ouverture", ""]
            L += [f"- {o['action']} {o['symbole']} : {o['statut']} ({o.get('resultat', '')})" for o in self.executions]
        if d["propositions"]:
            L += ["", "## Propositions des analystes", ""]
            for p in d["propositions"]:
                av = p.get("avis") or {}
                L.append(f"- `{p['id']}` {p['action']} {p['symbole']} · critique : {av.get('verdict', '—')} · "
                         f"{'**retenue**' if p.get('retenue') else 'non retenue'} — {p['these'][:200]}")
        if d["decision"]:
            L += ["", "## Décision du gérant", "", f"> {d['decision']}", ""]
        for aid, r in d["agents"].items():
            L += ["", f"### {r['nom']} ({r.get('modele') or '?'})",
                  f"{r.get('outils', 0)} appels d'outils, {r.get('duree_s', 0)} s, {r.get('tokens', 0)} tokens"
                  + (f" · **erreur** : {r['erreur']}" if r.get("erreur") else ""), "",
                  f"> {(r.get('compte_rendu') or '—')[:1500]}", ""]
            L += [f"- {o['action']} {o['symbole']} : {o.get('resultat', '')}" for o in r.get("ordres", [])]
        return "\n".join(L) + "\n"
