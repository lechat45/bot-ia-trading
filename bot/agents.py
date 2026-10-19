"""Les 4 IA d'Aywen, version Gemini + Groq, et le déroulé d'une séance.

Comme dans la vidéo :
  - chaque IA a son modèle, sa stratégie (skill « stratégie ») et son propre sous-compte ;
  - elle partage avec les autres le même socle de skills et les mêmes outils ;
  - elle travaille seule : elle choisit ses outils, prend des notes et passe ses ordres ;
  - son contexte est remis à zéro à chaque séance : ses notes sont sa seule mémoire.

Trois moments par jour de bourse :
  - 9 h (Paris)   PRÉPARATION : bourse de New York fermée, les ordres sont planifiés ;
  - 15 h 30       OUVERTURE   : le programme exécute les ordres planifiés au prix d'ouverture ;
  - fin d'après-midi SUIVI    : bourse ouverte, les IA font le point et agissent en direct.
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

from . import memory
from .agent_tools import SKILL_INFO, AgentEnv, Market, declarations
from .comptes import Comptes
from .executor import Broker
from .llm import ContextTooLarge, LLMError
from .risk import check_buy, check_sell

log = logging.getLogger("seance")
SKILLS = Path(__file__).resolve().parent.parent / "skills"
PARIS, NY = ZoneInfo("Europe/Paris"), ZoneInfo("America/New_York")
AGENT_DEADLINE_S = 25 * 60


@dataclass
class Agent:
    id: str
    nom: str
    provider: str
    key_index: int
    models: list[str] = field(default_factory=list)
    strategie: str = ""
    inspire_de: str = ""


AGENTS = [
    Agent("qualite", "Analyste Qualité", "gemini", 0,
          ["gemini-3.5-flash", "gemini-3.7-flash", "gemini-3.5-flash-lite"], "qualite", "Claude"),
    Agent("equilibre", "Analyste Équilibre", "gemini", 1,
          ["gemini-3.5-flash", "gemini-3.7-flash", "gemini-3.5-flash-lite"], "equilibre", "ChatGPT"),
    Agent("sentiment", "Analyste Sentiment", "groq", 0,
          ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"], "sentiment", "Grok"),
    Agent("contrarien", "Analyste Contrarien", "groq", 1,
          ["qwen/qwen3.8-27b", "openai/gpt-oss-20b", "openai/gpt-oss-120b"], "contrarien", "Mistral"),
]
MODES = {
    "preparation": "Préparation (bourse fermée, ordres planifiés pour l'ouverture)",
    "ouverture": "Ouverture (exécution des ordres planifiés)",
    "suivi": "Suivi (bourse ouverte, ordres immédiats)",
}


def _skill(name: str) -> str:
    return (SKILLS / "commun" / f"{name}.md").read_text(encoding="utf-8")


def _strategy(name: str) -> str:
    return (SKILLS / "strategies" / f"{name}.md").read_text(encoding="utf-8")


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
        self.now = dt.datetime.now(dt.timezone.utc)
        self.when = self.now.astimezone(PARIS).strftime("%Y-%m-%d %H:%M (Paris)")
        self.plan: dict = {}
        self.plan_lock = threading.Lock()
        self.new_notes: dict = {}
        self.results: dict = {}
        self.executions: list = []

    # ------------------------------------------------------------------ plan d'ouverture
    def add_plan(self, order: dict):
        with self.plan_lock:
            self.plan.setdefault("ordres", []).append(order)

    def cancel_plan(self, aid, sym) -> int:
        with self.plan_lock:
            n = 0
            for o in self.plan.get("ordres", []):
                if o["agent"] == aid and o["symbole"] == sym and o["statut"] == "en_attente":
                    o["statut"], o["resultat"] = "annule", "annulé par l'IA"
                    n += 1
            return n

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
            self.comptes = Comptes.load([a.id for a in AGENTS], equity, persist=not self.dry_run)
            self.comptes.sync(self.alpaca)
            self.broker = Broker(self.alpaca, self.comptes, self.dry_run)
            self.market = Market(self.alpaca, self.offline, self.now.astimezone(NY).date())
            self.journal = memory.recent_journal(10)
            self.before = {a.id: self.comptes.valuation(a.id, {}) for a in AGENTS}

            if self.mode == "ouverture":
                self.plan = memory.read_plan(simulation=self.offline)
                self.execute_plan()
            else:
                if self.mode == "preparation":
                    self.plan = {"date": self.trading_date, "cree_le": self.now.isoformat(timespec="seconds"),
                                 "simulation": self.dry_run, "ordres": []}
                with cf.ThreadPoolExecutor(max_workers=len(AGENTS)) as pool:
                    for a, res in zip(AGENTS, pool.map(self.run_agent, AGENTS)):
                        self.results[a.id] = res
            self.finish()
            return self.results
        finally:
            memory.state_stop()

    # ------------------------------------------------------------------ une IA
    def system_prompt(self, a: Agent) -> str:
        cfg = self.cfg
        paris = self.now.astimezone(PARIS).strftime("%A %d/%m/%Y %H:%M")
        ny = self.now.astimezone(NY).strftime("%H:%M")
        if self.market_open:
            moment = ("SÉANCE DE SUIVI : la bourse de New York est OUVERTE, tes ordres sont exécutés immédiatement. "
                      "Fais le point sur tes positions (thèse, stop, catalyseurs), puis agis si c'est justifié.")
        else:
            moment = ("SÉANCE DE PRÉPARATION : la bourse de New York est FERMÉE (ouverture à 15h30, heure de Paris). "
                      "Décide des actions à acheter ou vendre : tes ordres seront PLANIFIÉS puis exécutés "
                      "automatiquement à l'ouverture, au prix d'ouverture (annulés si le cours s'écarte de plus de "
                      f"{cfg.max_gap_pct:g} % du prix de ce matin). C'est MAINTENANT que tu décides de ce qui sera "
                      "acheté ou vendu à l'ouverture : si une thèse est prête, passe l'ordre pendant cette séance (la "
                      "suivante n'aura lieu qu'en fin d'après-midi). Ne rien faire reste valable si aucune thèse n'est prête.")
        skills = "\n".join(f"- {k} : {v}" for k, v in SKILL_INFO.items())
        return (
            f"Tu es « {a.nom} », une IA qui investit de façon autonome sur son propre sous-compte "
            "(paper trading chez Alpaca, argent virtuel, actions cotées aux États-Unis). Trois autres IA ont chacune "
            "leur sous-compte et leur stratégie ; vous ne communiquez pas.\n"
            f"Nous sommes le {paris} à Paris ({ny} à New York).\n{moment}\n\n"
            "Tu travailles seul avec tes outils : c'est toi qui décides lesquels utiliser et dans quel ordre. "
            "Tes notes sont ta seule mémoire entre deux séances. Termine TOUJOURS par terminer_session.\n"
            f"Tu disposes d'environ {cfg.max_steps_preparation if not self.market_open else cfg.max_steps_suivi} "
            "appels d'outils pour cette séance : analyse en profondeur peu d'idées et garde de quoi passer tes "
            "ordres et écrire tes notes.\n\n"
            f"{_skill('00-lisez-moi')}\n{_skill('routine-de-session')}\n{_strategy(a.strategie)}\n\n"
            f"SKILLS DISPONIBLES (outil lire_skill) :\n{skills}\n\n"
            f"LIMITES APPLIQUÉES PAR LE CODE : {cfg.max_position_pct:g} % max de ton sous-compte par titre ; "
            f"{cfg.min_cash_pct:g} % de liquidités gardées ; {cfg.max_positions} positions max ; {cfg.max_orders} ordres "
            f"max par séance ; stop loss obligatoire entre {cfg.min_stop_distance_pct:g} et {cfg.max_stop_distance_pct:g} % ; "
            f"objectif de gain ≥ {cfg.min_reward_risk:g} × le stop ; pas d'action sous {cfg.min_price:g} $ ; un stop ne "
            f"se descend jamais ; pas de rachat d'un titre vendu il y a moins de {cfg.anti_churn_days} jours ; "
            f"{cfg.max_web_searches} recherches web par séance. Réponds en français."
        )

    def opening(self, a: Agent) -> str:
        acct = self.comptes.agent(a.id)
        events = self.comptes.take_events(a.id, acct.get("derniere_seance"))
        notes = memory.read_notes(a.id) or "(aucune note : c'est ta toute première séance)"
        ev = "\n".join(f"- {e}" for e in events) or "- rien de particulier"
        return (f"Nouvelle séance : {MODES[self.mode]}.\n\n"
                f"TES NOTES (écrites lors de ta dernière séance) :\n{notes}\n\n"
                f"CE QUI S'EST PASSÉ SUR TON SOUS-COMPTE DEPUIS :\n{ev}\n\n"
                "Applique ta routine de séance avec tes outils.")

    def run_agent(self, a: Agent) -> dict:
        env = AgentEnv(self, a)
        start = time.time()
        system = self.system_prompt(a)
        tools = declarations(self.market_open)
        messages = [{"role": "user", "text": self.opening(a)}]
        env.log("notes", texte="Relit ses notes et les événements depuis la dernière séance")
        max_steps = self.cfg.max_steps_preparation if self.mode == "preparation" else self.cfg.max_steps_suivi
        budget = 14000 if a.provider == "groq" else 60000
        # En fin de séance, seuls les outils pour agir et conclure restent disponibles.
        final_tools = [t for t in tools if t["name"] in
                       ("passer_ordre", "annuler_ordre", "ajuster_stop", "ecrire_notes", "terminer_session")]
        nudged, reminded, final, final_turns, error, used = False, False, False, 0, None, ""
        while not env.done:
            if time.time() - start > AGENT_DEADLINE_S:
                error = "temps maximum de séance dépassé"
                break
            if not reminded and env.tool_calls >= max_steps - 4:
                reminded = True
                messages.append({"role": "user", "text": "Il te reste environ 4 appels d'outils : conclus ton analyse, "
                                                         "passe tes ordres si une thèse est prête, puis écris tes notes "
                                                         "et termine."})
            if not final and env.tool_calls >= max_steps:
                final = True
                messages.append({"role": "user", "text": "Tu as utilisé tous tes appels d'analyse : tu peux encore "
                                                         "passer tes ordres, mettre à jour tes notes, puis appelle "
                                                         "terminer_session."})
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
                messages.append({"role": "user", "text": "Continue ta routine avec tes outils, puis appelle "
                                                         "terminer_session avec ton compte rendu."})
                continue
            for c in msg["calls"]:
                messages.append({"role": "tool", "id": c["id"], "name": c["name"],
                                 "content": env.run(c["name"], c.get("args") or {})})
        if not env.done and not env.compte_rendu:
            env.compte_rendu = "(séance interrompue avant le compte rendu)"
        memory.state_agent(a.id, statut="termine" if not error else "erreur", action=(error or "")[:120])
        if not self.dry_run:
            with self.comptes.lock:
                self.comptes.agent(a.id)["derniere_seance"] = self.now.isoformat(timespec="seconds")
        log.info("%s : %d outils, %d ordres, %s", a.id, env.tool_calls, len(env.orders), error or "ok")
        return {"nom": a.nom, "modele": used, "etapes": env.steps, "compte_rendu": env.compte_rendu,
                "ordres": env.orders, "erreur": error, "duree_s": round(time.time() - start),
                "outils": env.tool_calls}

    # ------------------------------------------------------------------ ouverture
    def execute_plan(self):
        cfg, plan = self.cfg, self.plan
        if not plan.get("ordres"):
            log.info("Aucun ordre planifié.")
            return
        todo = [o for o in plan["ordres"] if o["statut"] == "en_attente"]
        todo.sort(key=lambda o: 0 if o["action"] == "vendre" else 1)  # les ventes libèrent du cash
        for o in todo:
            aid, sym = o["agent"], o["symbole"]
            price = self.market.price(sym)
            held = list(self.comptes.agent(aid)["positions"])
            val = self.comptes.valuation(aid, self.market.prices(held))
            if o["action"] == "acheter":
                ref = o.get("prix_reference") or price
                gap = (price / ref - 1) * 100 if price and ref else 0
                if not price:
                    o.update(statut="erreur", resultat="prix indisponible à l'ouverture")
                elif abs(gap) > cfg.max_gap_pct:
                    o.update(statut="annule", resultat=f"cours d'ouverture {price:.2f} $ trop éloigné du prix du matin "
                                                       f"{ref:.2f} $ ({gap:+.1f} %)")
                else:
                    ok, msg, d = check_buy(cfg, aid, val, sym, price, o["montant_usd"], o["stop_loss_pct"],
                                           o["take_profit_pct"], self.journal, clamp=True)
                    if not ok:
                        o.update(statut="rejete", resultat=msg)
                    else:
                        r = self.broker.buy(aid, sym, d["qty"], d["stop_loss_pct"], d["take_profit_pct"], o.get("these", ""))
                        o.update(statut="execute" if r["ok"] else "erreur", resultat=r["message"],
                                 prix_execution=r.get("prix"), qty=r.get("qty"))
            else:
                ok, msg, d = check_sell(cfg, aid, val, sym, o.get("pourcentage", 100), self.journal)
                if not ok:
                    o.update(statut="rejete", resultat=msg)
                else:
                    r = self.broker.sell(aid, sym, d["qty"], o.get("these", ""))
                    o.update(statut="execute" if r["ok"] else "erreur", resultat=r["message"],
                             prix_execution=r.get("prix"), qty=r.get("qty"))
            o["traite_le"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
            self.comptes.event(aid, f"Ouverture, ordre planifié {o['action']} {sym} : {o['resultat']}")
            memory.state_agent(aid, statut="outil", action=f"ouverture : {o['action']} {sym} → {o['statut']}")
            log.info("Ouverture %s %s %s : %s", aid, o["action"], sym, o["resultat"])
            self.executions.append(o)
        plan["execute_le"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

    # ------------------------------------------------------------------ fin de séance
    def finish(self):
        prices = self.market.prices(self.comptes.symbols())
        after = {a.id: self.comptes.valuation(a.id, prices) for a in AGENTS}
        if not self.dry_run:
            self.comptes.save()
            memory.append_history([{"date": self.now.isoformat(timespec="minutes"), "agent": a.id,
                                    "valeur": after[a.id]["valeur"], "cash": after[a.id]["cash"],
                                    "positions": len(after[a.id]["positions"])} for a in AGENTS])
        if self.mode in ("preparation", "ouverture") and self.plan:
            memory.write_plan(self.plan, simulation=self.dry_run)
        name = self.now.astimezone(PARIS).strftime("%Y-%m-%d_%H%M") + f"_{self.mode}" + ("_simulation" if self.dry_run else "")
        data = {
            "nom": name, "quand": self.when, "ts": self.now.isoformat(), "mode": self.mode,
            "simulation": self.dry_run, "marche_ouvert": self.market_open, "date_bourse": self.trading_date,
            "agents": {aid: {**r, "tokens": self.router.usage[aid]["tokens"], "appels": self.router.usage[aid]["appels"],
                             "valeur_avant": self.before[aid]["valeur"], "valeur_apres": after[aid]["valeur"]}
                       for aid, r in self.results.items()},
            "executions": self.executions,
            "plan": self.plan.get("ordres", []) if self.mode == "preparation" else [],
            "comptes": after,
            "cles": dict(self.router.slots),
            "recherche_web_tokens": self.router.usage["web"]["tokens"],
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
        L = [f"# Séance du {d['quand']} : {MODES[self.mode]}", "",
             f"Compte paper Alpaca{' · SIMULATION (aucun ordre envoyé)' if self.dry_run else ''}", "",
             "| IA | Valeur | Plus-value | Liquidités | Positions |", "|---|---|---|---|---|"]
        for a in AGENTS:
            v = d["comptes"][a.id]
            L.append(f"| {a.nom} | {v['valeur']:.2f} $ | {v['pl']:+.2f} $ ({v['pl_pct']:+.2f} %) | {v['cash']:.2f} $ | "
                     f"{', '.join(p['symbole'] for p in v['positions']) or '—'} |")
        if self.executions:
            L += ["", "## Ordres planifiés exécutés à l'ouverture", ""]
            L += [f"- **{o['agent']}** {o['action']} {o['symbole']} : {o['statut']} ({o.get('resultat', '')})"
                  for o in self.executions]
        for aid, r in d["agents"].items():
            L += ["", f"## {r['nom']} ({r.get('modele') or '?'})", "",
                  f"{r.get('outils', 0)} appels d'outils, {r.get('duree_s', 0)} s, {r.get('tokens', 0)} tokens"
                  + (f" · **erreur** : {r['erreur']}" if r.get("erreur") else ""), "",
                  f"> {r.get('compte_rendu') or '—'}", ""]
            L += [f"- {o['action']} {o['symbole']} : {o.get('resultat', '')}" for o in r.get("ordres", [])]
        return "\n".join(L) + "\n"
