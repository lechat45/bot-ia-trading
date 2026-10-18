"""Faux Alpaca et fausses IA pour tester tout le pipeline sans clé ni réseau (--offline)."""
import random

PRICES = {"AAPL": 200.0, "MSFT": 400.0, "NVDA": 120.0, "XOM": 110.0, "KO": 60.0}


class FakeAlpaca:
    def __init__(self):
        self.sent = []

    def account(self):
        return {"equity": "100000", "cash": "89000", "last_equity": "99500"}

    def clock(self):
        import datetime as dt

        now = dt.datetime.now(dt.timezone.utc)
        return {"is_open": True, "next_close": (now + dt.timedelta(hours=3, minutes=12)).isoformat(),
                "next_open": (now + dt.timedelta(hours=20)).isoformat()}

    def positions(self):
        return [{"symbol": "XOM", "qty": "100", "avg_entry_price": "105", "current_price": "110",
                 "market_value": "11000", "unrealized_plpc": "0.0476"}]

    def open_orders(self):
        return [{"id": "stop-xom", "symbol": "XOM", "side": "sell", "type": "stop", "stop_price": "100"},
                {"id": "tp-xom", "symbol": "XOM", "side": "sell", "type": "limit", "limit_price": "125"}]

    def portfolio_history(self, period="1M", timeframe="1D"):
        import time

        rnd, v, eq = random.Random(7), 100_000.0, []
        for _ in range(30):
            v *= 1 + rnd.gauss(0.0012, 0.006)
            eq.append(round(v, 2))
        eq[-1] = 100_000.0
        now = int(time.time())
        return {"timestamp": [now - (29 - i) * 86400 for i in range(30)], "equity": eq}

    def asset(self, s):
        return {"tradable": s in PRICES, "status": "active"}

    def bars(self, symbols, days=400):
        out = {}
        for s in symbols:
            rnd, p, rows = random.Random(s), PRICES.get(s, 50) * 0.8, []
            for _ in range(260):
                p *= 1 + rnd.gauss(0.0008, 0.015)
                rows.append({"o": p, "h": p * 1.01, "l": p * 0.99, "c": p, "v": rnd.randint(100_000, 1_000_000)})
            rows[-1]["c"] = PRICES.get(s, 50)
            out[s] = rows
        return out

    def snapshots(self, symbols):
        return {s: {"latestTrade": {"p": PRICES[s]}} for s in symbols if s in PRICES}

    def news(self, symbols=None, limit=20):
        return [{"created_at": "2026-10-16T14:00:00Z", "headline": "Apple dévoile un nouveau produit",
                 "symbols": ["AAPL"]}]

    def movers(self, top=15):
        return {"gainers": [{"symbol": "NVDA", "percent_change": 6.2, "price": 120.0}],
                "losers": [{"symbol": "KO", "percent_change": -4.1, "price": 60.0}]}

    def most_actives(self, top=20):
        return [{"symbol": "AAPL"}, {"symbol": "MSFT"}]


class FakeRouter:
    """Répond comme les IA, avec des ordres volontairement bons ET mauvais pour tester le risque."""

    def __init__(self):
        from collections import defaultdict

        self.tokens, self.calls = defaultdict(int), defaultdict(int)

    def ask(self, provider, key_index, system, user, *, search=False, label="", **_):
        slot = f"{provider}#{key_index + 1}"
        self.tokens[slot] += len(system + user) // 4
        self.calls[slot] += 1
        stage, agent = label.split(":")
        if stage == "selection":
            picks = {"qualite": ["AAPL", "MSFT"], "equilibre": ["KO", "AAPL"],
                     "sentiment": ["NVDA", "ZZZZ"], "contrarien": ["KO"]}
            return {"tickers": picks[agent], "raison": "test"}, slot + ":faux"
        if stage == "theses":
            return {"analyse": f"Analyse factice de {agent}.", "notes": f"Notes de {agent}.",
                    "propositions": [{"action": "acheter", "symbole": "AAPL", "poids_pct": 5,
                                      "stop_loss": 186, "take_profit": 230, "arguments": "test",
                                      "confiance": "moyen"}]}, slot + ":faux"
        if stage == "critique":
            return {"avis": [{"id": "qualite-1", "verdict": "ok", "raison": "test"}],
                    "risques_portefeuille": "aucun", "notes": "Notes critique."}, slot + ":faux"
        return {"synthese": "Décision factice.", "notes": "Journal de bord factice.", "ordres": [
            {"action": "acheter", "symbole": "AAPL", "poids_pct": 5, "stop_loss": 186, "take_profit": 230},
            {"action": "acheter", "symbole": "MSFT", "poids_pct": 50, "stop_loss": 395, "take_profit": 401},
            {"action": "ajuster_stop", "symbole": "XOM", "stop_loss": 95},
            {"action": "acheter", "symbole": "NVDA", "poids_pct": 8, "stop_loss": 110, "take_profit": 150},
        ]}, slot + ":faux"
