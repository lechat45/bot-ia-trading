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

from bot.agents import ANALYSTES, CRITIQUE, GERANT
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
                args, mode = ["--offline"], "demo"
            elif mode == "reel":
                args = []
            else:
                args, mode = ["--dry-run", "--force"], "simulation"
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


def _agent(a, role):
    keys = cfg.gemini_keys if a.provider == "gemini" else cfg.groq_keys
    return {"id": a.id, "nom": a.nom, "provider": a.provider, "cle": a.key_index + 1,
            "strategie": a.strategie, "role": role,
            "cle_configuree": DEMO or a.key_index < len(keys)}


def overview() -> dict:
    hit = _cache.get("overview")
    if hit and time.time() - hit[0] < 15 and not runner.running:
        return hit[1]
    out = {"demo": DEMO, "paper": cfg.paper,
           "agents": [_agent(a, "analyste") for a in ANALYSTES]
           + [_agent(CRITIQUE, "critique"), _agent(GERANT, "gerant")],
           "limites": {k: getattr(cfg, k) for k in (
               "max_position_pct", "min_cash_pct", "max_positions", "max_orders",
               "max_stop_distance_pct", "min_reward_risk")},
           "cles": {"gemini": len(cfg.gemini_keys), "groq": len(cfg.groq_keys),
                    "alpaca": not DEMO}}
    try:
        acct = broker.account()
        out["compte"] = {k: float(acct.get(k) or 0) for k in ("equity", "cash", "last_equity", "buying_power")}
        out["horloge"] = broker.clock()
        exits = {}
        for o in broker.open_orders():
            e = exits.setdefault(o["symbol"], {})
            if o["side"] == "sell" and o["type"] in ("stop", "stop_limit") and o.get("stop_price"):
                e["stop"] = max(float(o["stop_price"]), e.get("stop", 0))
            elif o["side"] == "sell" and o["type"] == "limit" and o.get("limit_price"):
                e["tp"] = float(o["limit_price"])
        out["positions"] = [{
            "symbole": p["symbol"], "qty": float(p["qty"]), "prix_achat": float(p["avg_entry_price"]),
            "prix": float(p["current_price"]), "valeur": float(p["market_value"]),
            "pl": float(p.get("unrealized_pl") or float(p["market_value"]) - float(p["qty"]) * float(p["avg_entry_price"])), "pl_pct": float(p["unrealized_plpc"]) * 100,
            **exits.get(p["symbol"], {})} for p in broker.positions()]
        h = broker.portfolio_history("1M", "1D")
        out["historique"] = [{"t": t, "v": v} for t, v in zip(h.get("timestamp") or [], h.get("equity") or [])
                             if v]  # Alpaca renvoie 0 avant le premier dépôt
    except Exception as e:  # on affiche l'erreur dans l'interface plutôt que de planter
        out["erreur"] = str(e)[:300]
    _cache["overview"] = (time.time(), out)
    return out


def sessions() -> list:
    rows = []
    for p in sorted((MEM / "sessions").glob("*.json"), reverse=True)[:60]:
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        rows.append({"nom": d.get("nom", p.stem), "quand": d.get("quand"), "simulation": d.get("simulation"),
                     "valeur": d.get("portefeuille", {}).get("valeur_totale"),
                     "ordres": len(d.get("ordres") or []), "rejets": len(d.get("rejets") or []),
                     "propositions": len(d.get("propositions") or []),
                     "synthese": (d.get("decision") or {}).get("synthese", "")[:220]})
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
