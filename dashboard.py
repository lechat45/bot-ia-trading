"""Tableau de bord local (l'équivalent de l'interface de pilotage d'Aywen).

    python dashboard.py            puis ouvrir http://127.0.0.1:8000

Sans clés Alpaca dans .env, il démarre en mode DÉMO avec de fausses données.
Le serveur n'écoute que sur ta machine (127.0.0.1) et n'affiche jamais les clés.
"""
import argparse
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

from bot import memory
from bot.agents import ACCOUNT, AGENTS
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
    keys = cfg.gemini_keys if provider == "gemini" else cfg.groq_keys
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


def _propositions() -> list[dict]:
    """Propositions d'achat des analystes (séances réelles), une seule par analyste, titre et jour."""
    rows = list(memory.read_propositions())
    for p in sorted((MEM / "sessions").glob("*.json"), key=lambda p: p.stem):  # séances d'avant ce registre
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if d.get("simulation") or d.get("hors_ligne"):
            continue
        rows += [{"date": d.get("date_bourse"), **x, "verdict": (x.get("avis") or {}).get("verdict")}
                 for x in d.get("propositions") or []]
    seen, out = set(), []
    for r in rows:
        key = (r.get("auteur"), r.get("symbole"), r.get("date"))
        if r.get("action") == "acheter" and r.get("prix_ref") and key not in seen:
            seen.add(key)
            out.append(r)
    return out


def classement() -> dict:
    """Ce qu'auraient rapporté les idées de chaque analyste depuis qu'il les a proposées (au prix du jour
    de la proposition), qu'elles aient été achetées ou non, et la justesse des avis du critique."""
    props = _propositions()
    if not props:
        return {"analystes": [], "propositions": 0}
    try:
        prices = broker.latest_prices(sorted({p["symbole"] for p in props}))
    except Exception:
        prices = {}
    for p in props:
        px = prices.get(p["symbole"])
        p["rendement"] = round((px / p["prix_ref"] - 1) * 100, 2) if px else None
    mean = lambda xs: round(sum(xs) / len(xs), 2) if xs else None  # noqa: E731
    rows = []
    for a in (x for x in AGENTS if x.role == "analyste"):
        mine = [p for p in props if p.get("auteur") == a.id and p["rendement"] is not None]
        r = [p["rendement"] for p in mine]
        best = max(mine, key=lambda p: p["rendement"], default=None)
        worst = min(mine, key=lambda p: p["rendement"], default=None)
        rows.append({"id": a.id, "propositions": len(mine), "retenues": sum(1 for p in mine if p.get("retenue")),
                     "rendement_moyen": mean(r), "reussite_pct": round(100 * sum(x > 0 for x in r) / len(r)) if r else None,
                     "moyenne_retenues": mean([p["rendement"] for p in mine if p.get("retenue")]),
                     "moyenne_ecartees": mean([p["rendement"] for p in mine if not p.get("retenue")]),
                     "meilleure": best and {"symbole": best["symbole"], "rendement": best["rendement"]},
                     "pire": worst and {"symbole": worst["symbole"], "rendement": worst["rendement"]}})
    rows.sort(key=lambda x: (x["rendement_moyen"] is None, -(x["rendement_moyen"] or 0)))
    judged = [p for p in props if p["rendement"] is not None and p.get("verdict") in ("ok", "rejet")]
    right = sum(1 for p in judged if (p["verdict"] == "ok") == (p["rendement"] > 0))
    return {"analystes": rows, "propositions": len(props), "depuis": min(p.get("date") or "" for p in props),
            "critique": {"avis": len(judged), "justes_pct": round(100 * right / len(judged)) if judged else None}}


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


def alertes() -> dict:
    """Frein d'urgence et écarts avec Alpaca relevés lors de la dernière séance réelle."""
    for p in sorted((MEM / "sessions").glob("*.json"), key=lambda p: p.stem, reverse=True):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not d.get("simulation"):
            return {"quand": d.get("quand"), "frein": d.get("frein"), "ecarts": d.get("ecarts") or []}
    return {}


def overview() -> dict:
    hit = _cache.get("overview")
    if hit and time.time() - hit[0] < 15 and not runner.running:
        return hit[1]
    out = {"demo": DEMO, "paper": cfg.paper, "agents": [_agent(a) for a in AGENTS],
           "limites": {k: getattr(cfg, k) for k in (
               "max_position_pct", "min_cash_pct", "max_positions", "max_orders", "max_stop_distance_pct",
               "min_reward_risk", "max_gap_pct", "preparation_heure")},
           "cles": {"gemini": sum(_key_ok("gemini", n) for n in (1, 2, 3)),
                    "groq": sum(_key_ok("groq", n) for n in (1, 2, 3)), "alpaca": not DEMO},
           "plan": memory.read_plan(simulation=DEMO) or memory.read_plan(simulation=True),
           "historique_ia": memory.read_history(), "installation": memory.read_installation(),
           "rappels": memory.read_rappels(), "bilan": memory.read_last_bilan(), "lecons": memory.read_lecons(),
           "alertes": alertes(),
           "ordres": [e for e in memory.recent_journal(120) if e.get("type") == "execution"][-300:]}
    try:
        acct = broker.account()
        out["compte"] = {k: float(acct.get(k) or 0) for k in ("equity", "cash", "last_equity", "buying_power")}
        out["horloge"] = broker.clock()
        prices = {p["symbol"]: float(p["current_price"]) for p in broker.positions()}
        out["equipe"] = _compte(out["compte"]["equity"], prices)
        out["positions"] = out["equipe"]["positions"]
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
