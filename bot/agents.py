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
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo

from . import memory, notify
from .agent_tools import SKILL_INFO, AgentEnv, Market, declarations
from .comptes import Comptes
from .executor import Broker
from .llm import ContextTooLarge, LLMError
from .risk import check_buy, check_sell

log = logging.getLogger("seance")
SKILLS = Path(__file__).resolve().parent.parent / "skills"
PARIS, NY = ZoneInfo("Europe/Paris"), ZoneInfo("America/New_York")
AGENT_DEADLINE_S = 20 * 60
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


class Session:
    def __init__(self, cfg, alpaca, router, mode: str, dry_run: bool, offline: bool = False):
        self.cfg, self.alpaca, self.router = cfg, alpaca, router
        self.mode, self.dry_run, self.offline = mode, dry_run, offline
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

    # ------------------------------------------------------------------ séance
    def run(self) -> dict:
        memory.state_start(self.mode, self.dry_run, [a.id for a in AGENTS])
        try:
            clock = self.alpaca.clock()
            self.market_open = bool(clock.get("is_open"))
            nxt = clock.get("next_open")
            self.trading_date = (self.now.astimezone(NY).date().isoformat() if self.market_open or not nxt
                                 else dt.datetime.fromisoformat(nxt.replace("Z", "+00:00")).astimezone(NY).date().isoformat())
            equity = float(self.alpaca.account()["equity"])
            self.comptes = Comptes.load([ACCOUNT], equity, persist=not self.dry_run)
            self.comptes.sync(self.alpaca)
            self.broker = Broker(self.alpaca, self.comptes, self.dry_run)
            self.market = Market(self.alpaca, self.offline, self.now.astimezone(NY).date())
            self.journal = memory.recent_journal(10)
            self.before = self.comptes.valuation(ACCOUNT, {})
            limit = (dt.date.fromisoformat(self.trading_date) - dt.timedelta(days=3)).isoformat()
            for r in self.rappels:  # un rappel non traité 3 jours après sa date expire
                if r["statut"] == "actif" and r["date"] < limit:
                    r["statut"] = "expire"

            if self.mode == "ouverture":
                self.plan = memory.read_plan(simulation=self.offline)
                self.execute_plan()
            else:
                if self.mode == "preparation":
                    self.plan = {"date": self.trading_date, "cree_le": self.now.isoformat(timespec="seconds"),
                                 "simulation": self.dry_run, "ordres": []}
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
        return c.max_steps_gerant

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
        skills = "\n".join(f"- {k} : {v}" for k, v in SKILL_INFO.items())
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
            f"{cfg.max_web_searches} recherches web par IA et par séance. Réponds en français."
        )

    def opening(self, a: Agent) -> str:
        notes = memory.read_notes(a.id) or "(aucune note : c'est ta toute première séance)"
        txt = f"Nouvelle séance : {MODES[self.mode]}.\n\nTES NOTES (écrites lors de ta dernière séance) :\n{notes}\n\n"
        txt += self.reminders_text()
        if a.role == "gerant":
            acct = self.comptes.agent(ACCOUNT)
            events = self.comptes.take_events(ACCOUNT, acct.get("derniere_seance"))
            txt += ("CE QUI S'EST PASSÉ SUR LE COMPTE DEPUIS LA DERNIÈRE SÉANCE :\n"
                    + ("\n".join(f"- {e}" for e in events) or "- rien de particulier") + "\n\n")
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
        budget = 14000 if a.provider == "groq" else 60000
        keep = {"passer_ordre", "annuler_ordre", "ajuster_stop", "proposer_ordre", "donner_avis",
                "ecrire_notes", "terminer_session"}
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
                                           o["take_profit_pct"], self.journal, clamp=True)
                    if not ok:
                        o.update(statut="rejete", resultat=msg)
                    else:
                        r = self.broker.buy(acct, sym, d["qty"], d["stop_loss_pct"], d["take_profit_pct"], o.get("these", ""))
                        o.update(statut="execute" if r["ok"] else "erreur", resultat=r["message"],
                                 prix_execution=r.get("prix"), qty=r.get("qty"))
            else:
                ok, msg, d = check_sell(cfg, acct, val, sym, o.get("pourcentage", 100), self.journal)
                if not ok:
                    o.update(statut="rejete", resultat=msg)
                else:
                    r = self.broker.sell(acct, sym, d["qty"], o.get("these", ""))
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
                "d'investissement personnalisé.")
        try:
            msg, used = self.router.chat(GERANT, "Tu es le gérant d'une équipe d'IA qui gère un compte de paper trading.",
                                         [{"role": "user", "text": user}], [], label="bilan")
        except LLMError as e:
            log.warning("bilan de la semaine impossible : %s", e)
            return ""
        texte = (msg.get("text") or "").strip()
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
            p["retenue"] = any(o.get("source") == p["id"] for o in self.results.get(GERANT.id, {}).get("ordres", []))
        name = self.now.astimezone(PARIS).strftime("%Y-%m-%d_%H%M") + f"_{self.mode}" + ("_simulation" if self.dry_run else "")
        data = {
            "nom": name, "quand": self.when, "ts": self.now.isoformat(), "mode": self.mode,
            "simulation": self.dry_run, "marche_ouvert": self.market_open, "date_bourse": self.trading_date,
            "agents": {aid: {**r, "tokens": self.router.usage[aid]["tokens"], "appels": self.router.usage[aid]["appels"]}
                       for aid, r in self.results.items()},
            "propositions": self.proposals,
            "decision": (self.results.get(GERANT.id) or {}).get("compte_rendu", ""),
            "executions": self.executions,
            "plan": self.plan.get("ordres", []) if self.mode == "preparation" else [],
            "compte": after, "valeur_avant": self.before["valeur"],
            "cles": dict(self.router.slots),
            "bilan": self.bilan,
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
