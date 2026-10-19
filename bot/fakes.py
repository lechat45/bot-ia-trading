"""Faux Alpaca et fausses IA pour tester tout le programme sans clé ni réseau (--offline).

Les fausses IA suivent la routine d'Aywen avec de vrais appels d'outils, y compris un ordre
volontairement mauvais pour vérifier que les garde-fous le refusent."""
import datetime as dt
import random
import re
import uuid
from collections import defaultdict

PRICES = {"AAPL": 200.0, "MSFT": 400.0, "NVDA": 120.0, "XOM": 110.0, "KO": 60.0, "SPY": 600.0,
          "ASML": 700.0, "STLA": 13.0, "MU": 90.0, "INTC": 30.0}


class FakeAlpaca:
    def __init__(self, open_: bool = True):
        self.open = open_
        self.orders: dict = {}

    # compte
    def account(self):
        return {"equity": "100000", "cash": "100000", "last_equity": "99500", "buying_power": "200000"}

    def clock(self):
        now = dt.datetime.now(dt.timezone.utc)
        return {"is_open": self.open, "next_close": (now + dt.timedelta(hours=3)).isoformat(),
                "next_open": (now + dt.timedelta(hours=6)).isoformat()}

    def positions(self):
        return []

    def open_orders(self):
        return [o for o in self.orders.values() if o["status"] in ("new", "held")]

    def portfolio_history(self, period="1M", timeframe="1D"):
        import time

        rnd, v, eq = random.Random(7), 100_000.0, []
        for _ in range(30):
            v *= 1 + rnd.gauss(0.0012, 0.006)
            eq.append(round(v, 2))
        now = int(time.time())
        return {"timestamp": [now - (29 - i) * 86400 for i in range(30)], "equity": eq}

    def asset(self, s):
        return {"tradable": s in PRICES, "status": "active"}

    # données
    def bars(self, symbols, days=400):
        out = {}
        for s in symbols:
            if s not in PRICES:
                continue
            rnd, p, rows = random.Random(s), PRICES[s] * 0.8, []
            for i in range(260):
                p *= 1 + rnd.gauss(0.0008, 0.015)
                rows.append({"t": f"2026-{1 + i // 22:02d}-01", "o": p, "h": p * 1.01, "l": p * 0.99, "c": p,
                             "v": rnd.randint(100_000, 1_000_000)})
            rows[-1]["c"] = PRICES[s]
            out[s] = rows
        return out

    def snapshots(self, symbols):
        return {s: {"latestTrade": {"p": PRICES[s]}} for s in symbols if s in PRICES}

    def latest_prices(self, symbols):
        return {s: PRICES[s] for s in symbols if s in PRICES}

    def news(self, symbols=None, limit=20):
        return [{"created_at": dt.datetime.now(dt.timezone.utc).isoformat(), "headline": "Apple dévoile un nouveau produit",
                 "summary": "Résumé factice.", "source": "test", "symbols": ["AAPL"]}]

    def movers(self, top=15):
        return {"gainers": [{"symbol": "NVDA", "percent_change": 6.2, "price": 120.0}],
                "losers": [{"symbol": "KO", "percent_change": -4.1, "price": 60.0}]}

    def most_actives(self, top=20):
        return [{"symbol": "AAPL", "volume": 1_000_000}, {"symbol": "MSFT", "volume": 800_000}]

    # ordres
    def _new(self, **kw):
        o = {"id": uuid.uuid4().hex, "status": "filled", **kw}
        self.orders[o["id"]] = o
        return o

    def submit_bracket(self, symbol, qty, stop, take_profit, client_id=None):
        stop_leg = self._new(symbol=symbol, side="sell", type="stop", stop_price=str(stop), status="held", qty=str(qty))
        tp_leg = self._new(symbol=symbol, side="sell", type="limit", limit_price=str(take_profit), status="new", qty=str(qty))
        return self._new(symbol=symbol, side="buy", type="market", filled_avg_price=str(PRICES[symbol]),
                         filled_qty=str(qty), legs=[stop_leg, tp_leg])

    def submit_market_sell(self, symbol, qty, client_id=None):
        return self._new(symbol=symbol, side="sell", type="market", filled_avg_price=str(PRICES[symbol]),
                         filled_qty=str(qty))

    def submit_exits(self, symbol, qty, stop, take_profit):
        stop_leg = self._new(symbol=symbol, side="sell", type="stop", stop_price=str(stop), status="held")
        return self._new(symbol=symbol, side="sell", type="limit", limit_price=str(take_profit), status="new",
                         legs=[stop_leg])

    def get_order(self, oid):
        return self.orders.get(oid, {"id": oid, "status": "canceled"})

    def cancel_order(self, oid):
        if oid in self.orders:
            self.orders[oid]["status"] = "canceled"
        return {}

    def replace_stop(self, oid, stop):
        old = self.orders[oid]
        old.update(status="replaced")
        new = self._new(**{k: v for k, v in old.items() if k not in ("id", "status")}, status="held")
        new["stop_price"] = str(stop)
        old["replaced_by"] = new["id"]
        return new


class FakeRouter:
    """Fausses IA : suivent la routine d'Aywen en appelant de vrais outils."""

    def __init__(self):
        self.usage = defaultdict(lambda: {"tokens": 0, "appels": 0})
        self.slots = defaultdict(lambda: {"tokens": 0, "appels": 0})

    def web_search(self, question, who="web"):
        self.usage[who]["appels"] += 1
        return {"reponse": f"Réponse factice à : {question}", "sources": ["exemple.com"]}

    def chat(self, agent, system, messages, tools, label=""):
        n = sum(1 for m in messages if m["role"] == "assistant")
        self.usage[agent.id]["tokens"] += sum(len(str(m)) for m in messages) // 4
        self.usage[agent.id]["appels"] += 1
        self.slots[f"{agent.provider}#{agent.key_index + 1}"]["appels"] += 1

        def call(name, **args):
            return {"id": f"c{n}-{name}", "name": name, "args": args}

        opening = messages[0]["text"]
        if agent.role == "critique":
            ids = sorted(set(re.findall(r'"id":"([a-z]+-\d+)"', opening)))
            script = [("Je vérifie les propositions une à une.",
                       [call("historique_prix", symbole="AAPL")]),
                      ("Voici mes verdicts.", [call("donner_avis", id=i, verdict="ok" if k % 2 == 0 else "reserve",
                                                    raison="test") for k, i in enumerate(ids)]),
                      ("", [call("terminer_session", compte_rendu=f"{len(ids)} propositions contrôlées.")])]
        elif agent.role == "gerant":
            script = [("Je fais le point sur le compte et les propositions.", [call("consulter_portefeuille")]),
                      ("Je retiens la proposition Qualité sur AAPL.",
                       [call("passer_ordre", action="acheter", symbole="AAPL", montant_usd=10000, stop_loss_pct=7,
                             take_profit_pct=15, these="Thèse factice retenue.", source="qualite-1"),
                        call("passer_ordre", action="acheter", symbole="MSFT", montant_usd=99000, stop_loss_pct=30,
                             take_profit_pct=10, these="Ordre volontairement mauvais (test des garde-fous).")]),
                      ("J'écris le journal de bord.", [call("ecrire_notes", contenu="Journal : AAPL planifié.")]),
                      ("", [call("terminer_session", compte_rendu="Décision factice : AAPL retenu.")])]
        else:
            sym = {"qualite": "AAPL", "equilibre": "KO", "sentiment": "NVDA", "contrarien": "ASML"}[agent.id]
            script = [
                ("Je relis mes notes puis je fais le point sur le portefeuille.",
                 [call("consulter_portefeuille"), call("screener", critere="baisse_semaine", limite=5)]),
                (f"{sym} ressort du screener, je regarde son historique et son actualité.",
                 [call("historique_prix", symbole=sym), call("actualites", symbole=sym, limite=3)]),
                ("Je vérifie le sentiment et une date précise.",
                 [call("sentiment_reseaux", symbole=sym), call("recherche_web", question=f"Date des résultats de {sym}")]),
                ("Je relis ma fiche sur le risque.", [call("lire_skill", nom="gestion-du-risque")]),
                ("Ma thèse est prête, je la propose au gérant.",
                 [call("proposer_ordre", action="acheter", symbole=sym, montant_usd=8000, stop_loss_pct=7,
                       take_profit_pct=15, these=f"Thèse factice sur {sym}.", confiance="moyen"),
                  call("proposer_ordre", action="acheter", symbole="MSFT", montant_usd=5000, stop_loss_pct=30,
                       take_profit_pct=10, these="Proposition volontairement mauvaise (test des garde-fous).")]),
                ("Je mets mes notes à jour.", [call("ecrire_notes", contenu=f"Idée : {sym} (thèse factice).")]),
                ("", [call("terminer_session", compte_rendu=f"Séance factice : proposition sur {sym}.")]),
            ]
        allowed = {t["name"] for t in tools}
        if "screener" not in allowed:  # fin de séance : seuls les outils pour agir et conclure sont proposés
            wrote = any(c["name"] == "ecrire_notes" for m in messages if m["role"] == "assistant" for c in m["calls"])
            text, calls = script[-1] if wrote else script[-2]
        else:
            text, calls = script[min(n, len(script) - 1)]
        return {"role": "assistant", "text": text, "calls": calls}, f"{agent.provider}#{agent.key_index + 1}:faux"
