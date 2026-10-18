"""Une session de trading : les 6 agents travaillent ensemble.

  1. Sélection  : les 4 analystes (une stratégie chacun) choisissent les titres à creuser
  2. Données    : le code récupère graphique, fondamentaux, actualités, Reddit
  3. Thèses     : chaque analyste propose des ordres argumentés
  4. Critique   : l'avocat du diable contrôle les propositions
  5. Gérant     : décision finale (avec recherche Google pour vérifier)
  6. Risque     : le code valide, puis envoie à Alpaca ; notes et rapport sauvegardés
"""
import datetime as dt
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from . import memory, tools
from .executor import execute
from .llm import LLMError
from .risk import SYMBOL_RE, Context, validate

log = logging.getLogger("session")
SKILLS = Path(__file__).resolve().parent.parent / "skills"
PARIS, NY = ZoneInfo("Europe/Paris"), ZoneInfo("America/New_York")
COMMON = ["00-lisez-moi", "routine-de-session", "fonctionnement-du-marche", "lecture-graphique",
          "analyse-fondamentale", "actualite-et-catalyseurs", "sentiment-reseaux",
          "gestion-du-risque", "stop-loss-take-profit", "execution-des-ordres", "notes-et-memoire"]
MAX_NEW_SYMBOLS = 12


@dataclass
class Agent:
    id: str
    nom: str
    provider: str
    key_index: int
    strategie: str
    search: bool = False


ANALYSTES = [
    Agent("qualite", "Analyste Qualité", "gemini", 0, "qualite"),
    Agent("equilibre", "Analyste Équilibre", "gemini", 1, "equilibre"),
    Agent("sentiment", "Analyste Sentiment", "groq", 0, "sentiment"),
    Agent("contrarien", "Analyste Contrarien", "groq", 1, "contrarien"),
]
CRITIQUE = Agent("critique", "Critique", "groq", 2, "critique")
GERANT = Agent("gerant", "Gérant", "gemini", 2, "gerant", search=True)

PROPOSAL_SCHEMA = """Réponds avec ce JSON :
{"analyse":"ton raisonnement en 3 à 6 phrases",
 "propositions":[{"action":"acheter|renforcer|vendre|alleger|ajuster_stop","symbole":"XXX",
   "poids_pct":5,"pourcentage":50,"stop_loss":0.0,"take_profit":0.0,"horizon_jours":20,
   "arguments":"faits datés et sourcés","risques":"...","invalidation":"prix ou fait",
   "confiance":"faible|moyen|eleve"}],
 "notes":"tes notes complètes mises à jour (elles remplacent les précédentes)"}
- poids_pct : % du portefeuille à investir (acheter/renforcer). pourcentage : % de la position à vendre (alleger).
- stop_loss / take_profit en dollars. ajuster_stop : seulement stop_loss (plus haut que l'actuel).
- "propositions" peut être vide si rien ne mérite d'agir : c'est une décision valable."""


def _skill(name: str) -> str:
    return (SKILLS / "commun" / f"{name}.md").read_text(encoding="utf-8")


def _strategy(name: str) -> str:
    return (SKILLS / "strategies" / f"{name}.md").read_text(encoding="utf-8")


def _dumps(x) -> str:
    return json.dumps(x, ensure_ascii=False, separators=(",", ":"))


class Session:
    def __init__(self, cfg, alpaca, router, dry_run: bool, offline: bool = False):
        self.cfg, self.alpaca, self.router = cfg, alpaca, router
        self.dry_run, self.offline = dry_run, offline
        self.now = dt.datetime.now(dt.timezone.utc)
        self.today = self.now.astimezone(NY).date()
        self.when = self.now.astimezone(PARIS).strftime("%Y-%m-%d %H:%M (Paris)")
        self.mode = "PAPER (argent virtuel)" if cfg.paper else "ARGENT RÉEL"
        self.outputs: dict[str, dict] = {}
        self.models: dict[str, str] = {}
        self.deep: dict[str, dict] = {}
        self.prices: dict[str, float] = {}

    # ------------------------------------------------------------------ prompts
    def _header(self, agent: Agent) -> str:
        paris = self.now.astimezone(PARIS).strftime("%A %d/%m/%Y %H:%M")
        ny = self.now.astimezone(NY).strftime("%H:%M")
        return (
            f"Tu es « {agent.nom} », l'un des 6 agents IA d'une équipe qui gère ensemble UN "
            f"portefeuille d'actions américaines chez Alpaca (compte {self.mode}). "
            f"Nous sommes le {paris} à Paris ({ny} à New York). Quatre analystes ont chacun une "
            "stratégie différente, un critique contrôle leurs idées, un gérant décide. "
            "Réponds UNIQUEMENT avec un objet JSON valide, en français, sans texte autour.\n\n"
        )

    def _limits(self) -> str:
        c = self.cfg
        return (
            "\n\nLIMITES APPLIQUÉES PAR LE CODE (tout ordre non conforme est rejeté) : "
            f"max {c.max_position_pct:g} % du portefeuille par titre ; {c.min_cash_pct:g} % de cash "
            f"minimum ; max {c.max_positions} positions ; max {c.max_orders} ordres par session ; "
            f"stop obligatoire entre {c.min_stop_distance_pct:g} % et {c.max_stop_distance_pct:g} % "
            f"sous le prix ; ratio gain/perte ≥ {c.min_reward_risk:g} ; prix ≥ {c.min_price:g} $ ; "
            "un stop ne se descend jamais ; pas de rachat d'un titre vendu il y a moins de "
            f"{c.anti_churn_days} jours ; pas de vente d'un titre acheté le jour même ; nombre "
            "entier d'actions ; actions US uniquement."
        )

    def _state(self, etape: str, agent: str | None = None, running: bool = True):
        """Ce que fait l'équipe en ce moment, lu par le tableau de bord."""
        memory.write_state({"running": running, "etape": etape, "agent": agent,
                            "debut": self.now.isoformat(), "simulation": self.dry_run,
                            "maj": dt.datetime.now(dt.timezone.utc).isoformat()})

    def _ask(self, agent: Agent, system: str, user: str, stage: str):
        label = f"{stage}:{agent.id}"
        self._state(stage, agent.id)
        try:
            out, used = self.router.ask(agent.provider, agent.key_index, system, user,
                                        search=agent.search, label=label)
            self.models[label] = used
            return out if isinstance(out, dict) else {}
        except LLMError as e:
            log.error("%s", e)
            self.models[label] = f"échec : {e}"
            return None

    # ------------------------------------------------------------------ données
    def load_portfolio(self):
        acct = self.alpaca.account()
        self.equity = float(acct["equity"])
        self.cash = float(acct["cash"])
        self.last_equity = float(acct.get("last_equity") or self.equity)
        self.positions = {}
        for p in self.alpaca.positions():
            qty = float(p["qty"])
            if qty <= 0:
                continue
            self.positions[p["symbol"]] = {
                "qty": qty, "avg": float(p["avg_entry_price"]), "price": float(p["current_price"]),
                "value": float(p["market_value"]), "pl_pct": round(float(p["unrealized_plpc"]) * 100, 1),
            }
            self.prices[p["symbol"]] = float(p["current_price"])
        self.exits, self.pending = {}, []
        for o in self.alpaca.open_orders():
            sym, side, typ = o["symbol"], o["side"], o["type"]
            ex = self.exits.setdefault(sym, {"stops": [], "tps": []})
            if side == "sell" and typ in ("stop", "stop_limit") and o.get("stop_price"):
                ex["stops"].append((o["id"], float(o["stop_price"])))
            elif side == "sell" and typ == "limit" and o.get("limit_price"):
                ex["tps"].append((o["id"], float(o["limit_price"])))
            else:
                self.pending.append(f"{side} {o.get('qty')} {sym} ({typ})")
        self.journal = memory.recent_journal(10)

    def portfolio_view(self) -> dict:
        rows = []
        for s, p in self.positions.items():
            ex = self.exits.get(s, {})
            rows.append({
                "symbole": s, "qty": p["qty"], "prix_achat": round(p["avg"], 2),
                "prix": round(p["price"], 2), "pl_pct": p["pl_pct"],
                "poids_pct": round(p["value"] / self.equity * 100, 1),
                "stop": max((x for _, x in ex.get("stops", [])), default=None),
                "take_profit": min((x for _, x in ex.get("tps", [])), default=None),
            })
        return {"valeur_totale": round(self.equity, 2), "cash": round(self.cash, 2),
                "cash_pct": round(self.cash / self.equity * 100, 1) if self.equity else 0,
                "variation_jour_pct": round((self.equity / self.last_equity - 1) * 100, 2) if self.last_equity else 0,
                "positions": rows, "ordres_en_attente": self.pending}

    def _safe(self, fn, default):
        try:
            return fn()
        except Exception as e:
            log.warning("donnée indisponible : %s", e)
            return default

    def load_market(self):
        mn = self.cfg.min_price
        mv = self._safe(lambda: self.alpaca.movers(15), {})

        def fmt(lst):
            return [{"s": m["symbol"], "var_pct": round(m.get("percent_change", 0), 1),
                     "prix": m.get("price")} for m in lst
                    if (m.get("price") or 0) >= mn and SYMBOL_RE.match(m["symbol"])][:10]

        actives = self._safe(lambda: self.alpaca.most_actives(20), [])
        news = self._safe(lambda: self.alpaca.news(limit=25), [])
        self.screener = {
            "plus_fortes_hausses": fmt(mv.get("gainers", [])),
            "plus_fortes_baisses": fmt(mv.get("losers", [])),
            "plus_actives": [a["symbol"] for a in actives if SYMBOL_RE.match(a["symbol"])][:15],
        }
        if not self.offline:
            top = sorted(tools.reddit_trending().values(), key=lambda x: x.get("rank", 999))[:10]
            self.screener["tendances_reddit_24h"] = [
                {"s": x["ticker"], "mentions": x.get("mentions"), "veille": x.get("mentions_24h_ago")}
                for x in top]
        self.headlines = [{"date": n.get("created_at", "")[:16], "titre": n.get("headline", "")[:150],
                           "symboles": n.get("symbols", [])[:4]} for n in news]

    def load_deep(self, picks: dict[str, list[str]]):
        held = list(self.positions)
        new: list[str] = []
        for lst in picks.values():
            for s in lst:
                if s not in held and s not in new:
                    new.append(s)
        tradable = []
        for s in new:
            a = self._safe(lambda s=s: self.alpaca.asset(s), {})
            if a.get("tradable") and a.get("status") == "active":
                tradable.append(s)
            else:
                log.info("%s ignoré (non négociable sur Alpaca)", s)
            if len(tradable) >= MAX_NEW_SYMBOLS:
                break
        symbols = held + tradable
        if not symbols:
            return
        bars = self._safe(lambda: self.alpaca.bars(symbols), {})
        snaps = self._safe(lambda: self.alpaca.snapshots(symbols), {})
        news = self._safe(lambda: self.alpaca.news(symbols, limit=50), [])
        for s in symbols:
            snap = snaps.get(s) or {}
            price = (snap.get("latestTrade") or {}).get("p") or (snap.get("dailyBar") or {}).get("c")
            if not price and bars.get(s):
                price = bars[s][-1]["c"]
            if price:
                self.prices[s] = float(price)
            ind = tools.indicators(bars.get(s, []))
            if price and "prix" in ind:
                ind["prix"] = round(float(price), 2)
            entry = {"graphique": ind,
                     "actus": [f"{n.get('created_at', '')[:10]} {n.get('headline', '')[:120]}"
                               for n in news if s in n.get("symbols", [])][:3]}
            if not self.offline:
                f = tools.fundamentals(s, self.today)
                if f:
                    entry["fondamentaux"] = f
                r = tools.reddit_sentiment(s)
                if r:
                    entry["reddit"] = r
            self.deep[s] = entry

    def _brief(self, s: str) -> dict:
        d = self.deep.get(s, {})
        g, f = d.get("graphique", {}), d.get("fondamentaux", {})
        keys_g = ("prix", "perf_1m_pct", "rsi14", "atr14", "sma50", "sma200")
        keys_f = ("secteur", "per_attendu", "jours_avant_resultats")
        return {**{k: g[k] for k in keys_g if k in g}, **{k: f[k] for k in keys_f if k in f}}

    def _journal_view(self, n=12):
        rows = [e for e in self.journal if e.get("type") == "execution"][-n:]
        return [f"{e['ts'][:10]} {e['action']} {e['symbole']} x{e.get('qty')} ({e.get('statut')})"
                for e in rows]

    # ------------------------------------------------------------------ étapes
    def round_selection(self) -> dict[str, list[str]]:
        picks = {}
        base_user = (
            f"PORTEFEUILLE : {_dumps(self.portfolio_view())}\n\n"
            f"SCREENER : {_dumps(self.screener)}\n\n"
            f"ACTUALITÉS RÉCENTES : {_dumps(self.headlines)}\n\n"
        )
        for a in ANALYSTES:
            system = self._header(a) + _skill("00-lisez-moi") + "\n" + _skill("routine-de-session") \
                + "\n" + _strategy(a.strategie)
            user = (f"TES NOTES DE LA DERNIÈRE SESSION :\n{memory.read_notes(a.id)}\n\n" + base_user +
                    "ÉTAPE 1/2 — SÉLECTION. Choisis jusqu'à 4 titres à étudier en profondeur selon TA "
                    "stratégie : positions actuelles à réexaminer, titres du screener ou des actualités, "
                    "ou de ta liste de surveillance (tout symbole d'action US). "
                    'Réponds : {"tickers":["XXX"],"raison":"1 à 2 phrases"}')
            out = self._ask(a, system, user, "selection") or {}
            tickers = [str(t).upper().strip().lstrip("$") for t in out.get("tickers", [])]
            picks[a.id] = [t for t in tickers if SYMBOL_RE.match(t)][:4]
            self.outputs[f"selection:{a.id}"] = {"tickers": picks[a.id], "raison": out.get("raison", "")}
            log.info("Sélection %s : %s", a.id, picks[a.id])
        return picks

    def round_theses(self, picks) -> list[dict]:
        proposals = []
        skills = "\n".join(_skill(n) for n in COMMON)
        for a in ANALYSTES:
            mine = [s for s in picks.get(a.id, []) if s in self.deep]
            data = {s: self.deep[s] for s in mine}
            others = {s: self._brief(s) for s in self.positions if s not in data}
            system = self._header(a) + skills + "\n\n" + _strategy(a.strategie) + self._limits()
            user = (
                f"TES NOTES :\n{memory.read_notes(a.id)}\n\n"
                f"PORTEFEUILLE : {_dumps(self.portfolio_view())}\n\n"
                f"DONNÉES DÉTAILLÉES DE TES TITRES : {_dumps(data)}\n\n"
                f"AUTRES POSITIONS (résumé) : {_dumps(others)}\n\n"
                f"DERNIÈRES OPÉRATIONS : {_dumps(self._journal_view())}\n\n"
                "ÉTAPE 2/2 — THÈSES. Applique la routine de session et ta stratégie.\n" + PROPOSAL_SCHEMA
            )
            out = self._ask(a, system, user, "theses")
            if out is None:
                continue
            self.outputs[f"theses:{a.id}"] = out
            for i, p in enumerate(out.get("propositions") or []):
                if isinstance(p, dict):
                    proposals.append({"id": f"{a.id}-{i + 1}", "auteur": a.id, **p})
        return proposals

    def round_critique(self, proposals) -> dict:
        if not proposals:
            return {}
        a = CRITIQUE
        syms = {str(p.get("symbole") or "").upper() for p in proposals} | set(self.positions)
        system = (self._header(a) + _skill("gestion-du-risque") + "\n" + _skill("stop-loss-take-profit")
                  + "\n" + _skill("actualite-et-catalyseurs") + "\n" + _strategy(a.strategie) + self._limits())
        user = (
            f"TES NOTES :\n{memory.read_notes(a.id)}\n\n"
            f"PORTEFEUILLE : {_dumps(self.portfolio_view())}\n\n"
            f"PROPOSITIONS DES ANALYSTES : {_dumps(proposals)}\n\n"
            f"DONNÉES CLÉS : {_dumps({s: self._brief(s) for s in syms if s in self.deep})}\n\n"
            f"DERNIÈRES OPÉRATIONS : {_dumps(self._journal_view())}\n\n"
            'Réponds : {"avis":[{"id":"...","verdict":"ok|reserve|rejet","raison":"..."}],'
            '"risques_portefeuille":"corrélations, concentration, cash…","notes":"tes notes mises à jour"}'
        )
        out = self._ask(a, system, user, "critique") or {}
        self.outputs["critique"] = out
        return out

    def round_gerant(self, proposals, critique) -> dict:
        if not proposals:
            log.info("Aucune proposition : le gérant n'est pas sollicité.")
            return {"synthese": "Aucune proposition des analystes : pas d'ordre.", "ordres": []}
        a = GERANT
        syms = {str(p.get("symbole") or "").upper() for p in proposals} | set(self.positions)
        system = self._header(a) + "\n".join(_skill(n) for n in COMMON) + "\n\n" \
            + _strategy(a.strategie) + self._limits()
        user = (
            f"JOURNAL DE BORD DE L'ÉQUIPE (tes notes) :\n{memory.read_notes(a.id)}\n\n"
            f"PORTEFEUILLE : {_dumps(self.portfolio_view())}\n\n"
            f"PROPOSITIONS : {_dumps(proposals)}\n\n"
            f"AVIS DU CRITIQUE : {_dumps(critique)}\n\n"
            f"DONNÉES CLÉS : {_dumps({s: self._brief(s) for s in syms if s in self.deep})}\n\n"
            f"DERNIÈRES OPÉRATIONS : {_dumps(self._journal_view())}\n\n"
            "Décide des ordres de cette session. Réponds avec ce JSON :\n"
            '{"synthese":"ta décision expliquée en 3 à 6 phrases",'
            '"ordres":[{"action":"acheter|renforcer|vendre|alleger|ajuster_stop","symbole":"XXX",'
            '"poids_pct":5,"pourcentage":50,"stop_loss":0.0,"take_profit":0.0,'
            '"source":"id de la proposition retenue","justification":"..."}],'
            '"notes":"journal de bord mis à jour : positions et thèses, calendrier daté, leçons"}'
        )
        out = self._ask(a, system, user, "gerant")
        if out is None:
            return {"synthese": "Le gérant n'a pas pu répondre : aucun ordre par sécurité.", "ordres": []}
        self.outputs["gerant"] = out
        return out

    # ------------------------------------------------------------------ exécution
    def apply(self, decision):
        ctx = Context(equity=self.equity, cash=self.cash, positions=self.positions,
                      prices=self.prices, exits=self.exits, journal=self.journal)
        approved, rejected = validate(decision.get("ordres") or [], ctx, self.cfg)
        results = execute(self.alpaca, approved, ctx, self.dry_run)
        if self.dry_run:
            return results, rejected
        ts = self.now.isoformat()
        memory.append_journal(
            [{"type": "execution", "ts": ts, **{k: r.get(k) for k in (
                "action", "symbole", "qty", "stop_loss", "take_profit", "montant", "statut",
                "source", "erreur")}} for r in results]
            + [{"type": "rejet", "ts": ts, "action": r.get("action"), "symbole": r.get("symbole"),
                "raison": r.get("raison_rejet")} for r in rejected]
        )
        return results, rejected

    def run(self):
        try:
            self._state("portefeuille")
            self.load_portfolio()
            self._state("marche")
            self.load_market()
            picks = self.round_selection()
            self._state("donnees")
            self.load_deep(picks)
            proposals = self.round_theses(picks)
            critique = self.round_critique(proposals)
            decision = self.round_gerant(proposals, critique)
            self._state("ordres")
            results, rejected = self.apply(decision)
            self.finish(proposals, decision, results, rejected)
            return results, rejected
        finally:
            self._state("termine", running=False)

    def finish(self, proposals, decision, results, rejected):
        if not self.dry_run:  # une simulation ne doit pas polluer la mémoire des agents
            for a in ANALYSTES:
                memory.write_notes(a.id, (self.outputs.get(f"theses:{a.id}") or {}).get("notes", ""), self.when)
            memory.write_notes("critique", self.outputs.get("critique", {}).get("notes", ""), self.when)
            memory.write_notes("gerant", decision.get("notes", ""), self.when)
            memory.append_history({"date": self.when[:16], "valeur": round(self.equity, 2),
                                   "cash": round(self.cash, 2), "positions": len(self.positions)})
        report = self.report(proposals, decision, results, rejected)
        name = self.now.astimezone(PARIS).strftime("%Y-%m-%d_%H%M") + ("_simulation" if self.dry_run else "")
        path = memory.write_report(name, report)
        memory.write_session_json(name, {
            "nom": name, "quand": self.when, "ts": self.now.isoformat(), "mode": self.mode,
            "simulation": self.dry_run, "portefeuille": self.portfolio_view(),
            "screener": getattr(self, "screener", {}), "titres_etudies": list(self.deep),
            "sorties": self.outputs, "modeles": self.models, "propositions": proposals,
            "decision": decision, "ordres": results, "rejets": rejected,
            "tokens": dict(self.router.tokens), "appels": dict(self.router.calls),
        })
        summary = os.getenv("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a", encoding="utf-8") as f:
                f.write(report)
        log.info("Rapport : %s", path)

    def report(self, proposals, decision, results, rejected) -> str:
        pv = self.portfolio_view()
        L = [f"# Session du {self.when}", "",
             f"**Mode :** {self.mode}{' — SIMULATION (aucun ordre envoyé)' if self.dry_run else ''}  ",
             f"**Valeur :** {pv['valeur_totale']} $ · **Cash :** {pv['cash']} $ ({pv['cash_pct']} %) · "
             f"**Jour :** {pv['variation_jour_pct']} %", "", "## Portefeuille", ""]
        if pv["positions"]:
            L += ["| Titre | Qté | Achat | Prix | P/L % | Poids % | Stop | TP |", "|---|---|---|---|---|---|---|---|"]
            L += [f"| {p['symbole']} | {p['qty']:g} | {p['prix_achat']} | {p['prix']} | {p['pl_pct']} | "
                  f"{p['poids_pct']} | {p['stop'] or '—'} | {p['take_profit'] or '—'} |" for p in pv["positions"]]
        else:
            L.append("_Aucune position._")
        L += ["", "## 1. Sélection des analystes", ""]
        for a in ANALYSTES:
            s = self.outputs.get(f"selection:{a.id}", {})
            L.append(f"- **{a.nom}** ({self.models.get('selection:' + a.id, '?')}) : "
                     f"{', '.join(s.get('tickers', [])) or '—'} — {s.get('raison', '')}")
        L += ["", "## 2. Thèses", ""]
        for a in ANALYSTES:
            out = self.outputs.get(f"theses:{a.id}")
            L.append(f"### {a.nom} — {self.models.get('theses:' + a.id, '?')}")
            if not out:
                L += ["_Pas de réponse._", ""]
                continue
            L += [out.get("analyse", ""), ""]
            for p in out.get("propositions") or []:
                if isinstance(p, dict):
                    L.append(f"- **{p.get('action')} {p.get('symbole')}** (poids {p.get('poids_pct')} %, "
                             f"stop {p.get('stop_loss')}, TP {p.get('take_profit')}, confiance "
                             f"{p.get('confiance')}) : {p.get('arguments', '')} — *Risques :* {p.get('risques', '')}")
            L.append("")
        c = self.outputs.get("critique")
        if c:
            L += ["## 3. Critique", "", f"_{self.models.get('critique:critique', '?')}_", ""]
            L += [f"- `{v.get('id')}` **{v.get('verdict')}** : {v.get('raison')}" for v in c.get("avis", [])
                  if isinstance(v, dict)]
            L += ["", f"**Risques du portefeuille :** {c.get('risques_portefeuille', '')}", ""]
        L += ["## 4. Décision du gérant", "", f"_{self.models.get('gerant:gerant', '—')}_", "",
              decision.get("synthese", ""), "", "## 5. Ordres", ""]
        for r in results:
            L.append(f"- ✅ **{r['action']} {r['symbole']}** x{r.get('qty')} — {r.get('statut')}"
                     f"{' : ' + r['erreur'] if r.get('erreur') else ''}")
        for r in rejected:
            L.append(f"- ⛔ {r.get('action')} {r.get('symbole')} — rejeté : {r.get('raison_rejet')}")
        if not results and not rejected:
            L.append("_Aucun ordre._")
        L += ["", "## Consommation (gratuite)", ""]
        L += [f"- {slot} : {self.router.calls[slot]} appels, {tok} tokens" for slot, tok in sorted(self.router.tokens.items())]
        return "\n".join(L) + "\n"
