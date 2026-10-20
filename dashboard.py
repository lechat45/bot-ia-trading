"""Tableau de bord local (l'équivalent de l'interface de pilotage d'Aywen).

    python dashboard.py            puis ouvrir http://127.0.0.1:8000

Sans clés Alpaca dans .env, il démarre en mode DÉMO avec de fausses données.
Le serveur n'écoute que sur ta machine (127.0.0.1) et n'affiche jamais les clés.
"""
import argparse
import datetime as dt
import collections
import json
import os
import re
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from bot import classement as ranking
from bot import memory, tools
from bot.agents import ACCOUNT, AGENTS, assign_providers
from bot.comptes import PATH as COMPTES_PATH
from bot.comptes import Comptes
from bot.config import Config

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "dashboard"
MEM = ROOT / "memoire"
NAME_RE = re.compile(r"^[\w\-]+$")
TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".js": "application/javascript; charset=utf-8", ".svg": "image/svg+xml"}

cfg = Config.from_env()
assign_providers(cfg)
DEMO = not (cfg.alpaca_key and cfg.alpaca_secret)
if DEMO:
    from bot.fakes import FakeAlpaca

    broker = FakeAlpaca()
else:
    from bot.alpaca import Alpaca

    broker = Alpaca(cfg.alpaca_key, cfg.alpaca_secret, cfg.paper)


class Runner:
    """Lance main.py en arrière-plan et garde ses derniers logs (bouton « play »)."""

    def __init__(self):
        self.proc, self.mode, self.started = None, None, None
        self.logs = collections.deque(maxlen=400)
        self.lock = threading.Lock()

    @property
    def running(self):
        return self.proc is not None and self.proc.poll() is None

    def start(self, mode: str) -> str | None:
        with self.lock:
            if self.running:
                return "Une session tourne déjà."
            if DEMO:
                args, mode = ["--offline", "--force"], "demo"
            elif mode == "reel":
                args = ["--mode", "auto", "--force"]
            else:
                args, mode = ["--mode", "auto", "--dry-run", "--force"], "simulation"
            env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
            self.logs.clear()
            self.proc = subprocess.Popen(
                [sys.executable, "main.py", *args], cwd=ROOT, env=env, text=True,
                encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.mode, self.started = mode, time.time()
            threading.Thread(target=self._pump, daemon=True).start()
            return None

    def _pump(self):
        for line in self.proc.stdout:
            self.logs.append(line.rstrip())
        self.proc.wait()
        self.logs.append(f"— session terminée (code {self.proc.returncode}) —")

    def view(self):
        return {"running": self.running, "mode": self.mode, "debut": self.started,
                "code": None if self.proc is None or self.running else self.proc.returncode,
                "logs": list(self.logs)[-250:]}


runner = Runner()
_cache: dict = {}


def _key_ok(provider: str, n: int) -> bool:
    """Une clé est « configurée » si elle est présente ici, ou si la dernière vérification l'a validée."""
    keys = {"gemini": cfg.gemini_keys, "groq": cfg.groq_keys, "mistral": cfg.mistral_keys}.get(provider, [])
    if n <= len(keys):
        return True
    checks = memory.read_installation().get("checks") or []
    return any(c.get("id") == f"cle_{provider}_{n}" and c.get("ok") for c in checks)


def _agent(a):
    return {"id": a.id, "nom": a.nom, "role": a.role, "provider": a.provider, "cle": a.key_index + 1,
            "modele": a.models[0], "strategie": a.strategie, "inspire_de": a.inspire_de,
            "cle_configuree": DEMO or _key_ok(a.provider, a.key_index + 1)}


def _compte(equity: float, prices: dict) -> dict:
    """Valeur du compte de l'équipe et positions (avec leur thèse, leur stop et leur objectif)."""
    if COMPTES_PATH.exists():
        c = Comptes(json.loads(COMPTES_PATH.read_text(encoding="utf-8")), persist=False)
        demarre = True
    else:
        c, demarre = Comptes.load([ACCOUNT], equity or 100_000, persist=False), False
    missing = [s for s in c.symbols() if s not in prices]
    if missing:
        try:
            prices = {**prices, **broker.latest_prices(missing)}
        except Exception:
            pass
    v = c.valuation(ACCOUNT, prices)
    v["demarre"] = demarre
    return v


def classement() -> dict:
    """Ce qu'auraient rapporté les idées de chaque analyste depuis qu'il les a proposées (bot/classement.py)."""
    props = ranking.load_propositions()
    try:
        prices = broker.latest_prices(sorted({p["symbole"] for p in props})) if props else {}
    except Exception:
        prices = {}
    return ranking.compute(props, prices, [a.id for a in AGENTS if a.role == "analyste"])


def performance(spy: list) -> dict:
    """Statistiques du compte : plus forte baisse, ventes gagnantes, performance comparée au S&P 500."""
    out = {}
    try:
        h = broker.portfolio_history("1A", "1D")
        eq = [(t, v) for t, v in zip(h.get("timestamp") or [], h.get("equity") or []) if v]
    except Exception:
        eq = []
    if COMPTES_PATH.exists():  # on compte depuis la création du compte de l'équipe
        start = json.loads(COMPTES_PATH.read_text(encoding="utf-8")).get("cree_le", "")[:10]
        kept = [(t, v) for t, v in eq if time.strftime("%Y-%m-%d", time.gmtime(t)) >= start]
        eq = kept if len(kept) >= 2 else eq[-2:]
    if len(eq) >= 2:
        peak, dd = eq[0][1], 0.0
        for _, v in eq:
            peak = max(peak, v)
            dd = min(dd, (v / peak - 1) * 100)
        d0 = time.strftime("%Y-%m-%d", time.gmtime(eq[0][0]))
        out.update(debut=d0, drawdown_max_pct=round(dd, 2), perf_pct=round((eq[-1][1] / eq[0][1] - 1) * 100, 2))
        s = [b for b in spy if b["t"] >= d0]
        if len(s) >= 2:
            out["spy_pct"] = round((s[-1]["c"] / s[0]["c"] - 1) * 100, 2)
    sells = [e for e in memory.recent_journal(3650) if e.get("type") == "execution" and e.get("statut") == "exécuté"
             and e.get("action") in ("vendre", "alleger") and e.get("plus_value") is not None]
    gains = [e["plus_value"] for e in sells if e["plus_value"] > 0]
    losses = [e["plus_value"] for e in sells if e["plus_value"] <= 0]
    out.update(ventes=len(sells), gagnantes=len(gains),
               reussite_pct=round(100 * len(gains) / len(sells)) if sells else None,
               gain_moyen=round(sum(gains) / len(gains), 2) if gains else None,
               perte_moyenne=round(sum(losses) / len(losses), 2) if losses else None,
               realise=round(sum(gains) + sum(losses), 2))
    return out


SECTEURS_FR = {"Technology": "Technologie", "Communication Services": "Communication",
               "Consumer Cyclical": "Consommation cyclique", "Consumer Defensive": "Consommation de base",
               "Financial Services": "Finance", "Healthcare": "Santé", "Industrials": "Industrie",
               "Energy": "Énergie", "Basic Materials": "Matériaux", "Utilities": "Services publics",
               "Real Estate": "Immobilier"}
_secteurs: dict = {}


def _secteur(sym: str) -> str:
    """Secteur d'un titre : la carte de l'univers d'abord, sinon Yahoo Finance (gardé en mémoire)."""
    if sym not in _secteurs:
        s = tools.INDUSTRIES.get(sym, {}).get("secteur")
        if not s:
            try:
                s = (tools.fundamentals(sym, dt.date.today()) or {}).get("secteur")
            except Exception:
                s = None
        _secteurs[sym] = SECTEURS_FR.get(s, s or "Autre")
    return _secteurs[sym]


def repartition(e: dict) -> dict:
    """Répartition du compte de l'équipe par secteur, liquidités comprises (camembert de l'Accueil)."""
    total = e.get("valeur") or 0
    groups: dict = {}
    for p in e.get("positions") or []:
        g = groups.setdefault(_secteur(p["symbole"]), {"valeur": 0.0, "symboles": []})
        g["valeur"] += p.get("valeur") or 0
        g["symboles"].append(p["symbole"])
    rows = [{"secteur": k, "valeur": round(v["valeur"], 2), "symboles": v["symboles"],
             "pct": round(v["valeur"] / total * 100, 1) if total else 0} for k, v in groups.items()]
    rows.sort(key=lambda r: -r["valeur"])
    cash = e.get("cash") or 0
    return {"secteurs": rows, "liquidites": round(cash, 2), "liquidites_pct": round(cash / total * 100, 1) if total else 0,
            "total": round(total, 2)}


def alertes() -> dict:
    """Frein d'urgence et écarts avec Alpaca relevés lors de la dernière séance réelle."""
    for p in sorted((MEM / "sessions").glob("*.json"), key=lambda p: p.stem, reverse=True):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not d.get("simulation"):
            return {"quand": d.get("quand"), "ts": d.get("ts"), "mode": d.get("mode"), "frein": d.get("frein"),
                    "ecarts": d.get("ecarts") or []}
    return {}


def quotas() -> dict:
    """Clés et modèles d'IA saturés en ce moment, et consommation de chaque clé aujourd'hui."""
    q = memory.read_quotas()
    now = time.time()
    sat = []
    for k, until in (q.get("satures") or {}).items():
        if float(until) > now:
            prov, ki, model = k.split("|", 2)
            sat.append({"cle": f"{prov} n°{int(ki) + 1}", "modele": model,
                        "jusqu_a": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(float(until)))})
    days = q.get("jours") or {}
    last = max(days) if days else None
    return {"satures": sat, "jour": last, "consommation": days.get(last, {}) if last else {}}


def trading_days() -> list[str]:
    """Jours de bourse de New York autour d'aujourd'hui : le site en ligne s'en sert pour repérer une séance
    manquée (il est calculé à la publication, mais vérifié par le navigateur à l'heure où on le regarde)."""
    today = time.gmtime()
    start = time.strftime("%Y-%m-%d", time.gmtime(time.mktime(today) - 10 * 86400))
    end = time.strftime("%Y-%m-%d", time.gmtime(time.mktime(today) + 20 * 86400))
    try:
        return [d["date"] for d in broker.calendar(start, end)]
    except Exception:
        return []


def overview() -> dict:
    hit = _cache.get("overview")
    if hit and time.time() - hit[0] < 15 and not runner.running:
        return hit[1]
    out = {"demo": DEMO, "paper": cfg.paper, "agents": [_agent(a) for a in AGENTS],
           "limites": {k: getattr(cfg, k) for k in (
               "max_position_pct", "min_cash_pct", "max_positions", "max_orders", "max_stop_distance_pct",
               "min_reward_risk", "max_gap_pct", "preparation_heure")},
           "cles": {"gemini": sum(_key_ok("gemini", n) for n in (1, 2, 3)),
                    "groq": sum(_key_ok("groq", n) for n in (1, 2, 3)),
                    "mistral": sum(_key_ok("mistral", n) for n in (1, 2, 3)), "alpaca": not DEMO},
           "plan": memory.read_plan(simulation=DEMO) or memory.read_plan(simulation=True),
           "historique_ia": memory.read_history(), "installation": memory.read_installation(),
           "rappels": memory.read_rappels(), "bilan": memory.read_last_bilan(), "lecons": memory.read_lecons(),
           "alertes": alertes(), "jours_bourse": trading_days(), "quotas": quotas(),
           # date du VRAI plan (pas celui d'une simulation) : sert à repérer une préparation manquée
           "plan_reel": memory.read_plan(simulation=DEMO).get("date"),
           "ordres": [e for e in memory.recent_journal(120) if e.get("type") == "execution"][-300:]}
    try:
        acct = broker.account()
        out["compte"] = {k: float(acct.get(k) or 0) for k in ("equity", "cash", "last_equity", "buying_power")}
        out["horloge"] = broker.clock()
        prices = {p["symbol"]: float(p["current_price"]) for p in broker.positions()}
        out["equipe"] = _compte(out["compte"]["equity"], prices)
        out["positions"] = out["equipe"]["positions"]
        out["repartition"] = repartition(out["equipe"])
        try:  # le S&P 500 (fonds SPY) pour comparer la performance du compte au marché
            spy = [{"t": str(b.get("t", ""))[:10], "c": b["c"]}
                   for b in (broker.bars(["SPY"], days=400) or {}).get("SPY") or []]
        except Exception:
            spy = []
        out["spy"] = spy[-31:]
        out["stats"] = performance(spy)
        out["classement"] = classement()
        h = broker.portfolio_history("1M", "1D")
        out["historique"] = [{"t": t, "v": v} for t, v in zip(h.get("timestamp") or [], h.get("equity") or [])
                             if v]  # Alpaca renvoie 0 avant le premier dépôt
    except Exception as e:  # on affiche l'erreur dans l'interface plutôt que de planter
        out["erreur"] = str(e)[:300]
    _cache["overview"] = (time.time(), out)
    return out


def sessions() -> list:
    rows = []
    # le nom d'une séance commence par sa date (la date des fichiers est fausse après un clone Git)
    for p in sorted((MEM / "sessions").glob("*.json"), key=lambda p: p.stem, reverse=True)[:60]:
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if "propositions" not in d:
            continue  # ancien format
        ag = d.get("agents") or {}
        rows.append({"nom": d.get("nom", p.stem), "quand": d.get("quand"), "mode": d.get("mode"),
                     "simulation": d.get("simulation"), "propositions": len(d.get("propositions") or []),
                     "ordres": sum(len(r.get("ordres") or []) for r in ag.values()) + len(d.get("executions") or []),
                     "erreurs": sum(1 for r in ag.values() if r.get("erreur")),
                     "decision": (d.get("decision") or "")[:200]})
    return rows


def notes() -> dict:
    out = {}
    for p in (MEM / "notes").glob("*.md"):
        out[p.stem] = p.read_text(encoding="utf-8")
    return out


def state() -> dict:
    try:
        etat = json.loads((MEM / "etat.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        etat = {}
    return {"etat": etat, "runner": runner.view()}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body: bytes, ctype="application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data, code=200):
        self._send(code, json.dumps(data, ensure_ascii=False, default=str).encode("utf-8"))

    def do_GET(self):
        url = urlparse(self.path)
        q = parse_qs(url.query)
        routes = {"/api/overview": overview, "/api/sessions": sessions, "/api/notes": notes,
                  "/api/state": state}
        if url.path in routes:
            return self._json(routes[url.path]())
        if url.path == "/api/session":
            name = (q.get("nom") or [""])[0]
            p = MEM / "sessions" / f"{name}.json"
            if not NAME_RE.match(name) or not p.exists():
                return self._json({"erreur": "session introuvable"}, 404)
            return self._send(200, p.read_bytes())
        path = "index.html" if url.path in ("/", "") else url.path.lstrip("/")
        f = (WEB / path).resolve()
        if WEB.resolve() not in f.parents or not f.is_file():
            return self._send(404, b"introuvable", "text/plain")
        self._send(200, f.read_bytes(), TYPES.get(f.suffix, "application/octet-stream"))

    def do_POST(self):
        if urlparse(self.path).path != "/api/run":
            return self._send(404, b"", "text/plain")
        # Protection basique : seule la page du tableau de bord peut lancer une session.
        origin = self.headers.get("Origin", "")
        if origin and not re.match(r"^http://(127\.0\.0\.1|localhost):\d+$", origin):
            return self._json({"erreur": "origine refusée"}, 403)
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            body = {}
        err = runner.start(body.get("mode", "simulation"))
        self._json({"ok": err is None, "erreur": err})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}"
    print(f"Tableau de bord : {url}  ({'DÉMO, fausses données' if DEMO else 'compte Alpaca ' + ('PAPER' if cfg.paper else 'RÉEL')})")
    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
