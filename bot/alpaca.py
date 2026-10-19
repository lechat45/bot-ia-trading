"""Accès à Alpaca : compte, ordres (broker) et données de marché gratuites (flux IEX)."""
import datetime as dt
import logging

import requests

log = logging.getLogger("alpaca")


class AlpacaError(Exception):
    pass


def _px(x: float) -> str:
    return f"{x:.2f}" if x >= 1 else f"{x:.4f}"


class Alpaca:
    DATA = "https://data.alpaca.markets"

    def __init__(self, key: str, secret: str, paper: bool = True):
        self.base = "https://paper-api.alpaca.markets" if paper else "https://api.alpaca.markets"
        self.s = requests.Session()
        self.s.headers.update({"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret})

    def _req(self, method, url, **kw):
        r = self.s.request(method, url, timeout=30, **kw)
        if r.status_code >= 400:
            raise AlpacaError(f"{method} {url.split('.markets')[-1]} -> {r.status_code} {r.text[:300]}")
        return r.json() if r.text.strip() else {}

    # ---- Compte ----
    def account(self):
        return self._req("GET", f"{self.base}/v2/account")

    def clock(self):
        return self._req("GET", f"{self.base}/v2/clock")

    def calendar(self, start: str, end: str) -> list:
        """Jours de bourse de New York entre deux dates (AAAA-MM-JJ), jours fériés exclus."""
        return self._req("GET", f"{self.base}/v2/calendar", params={"start": start, "end": end})

    def positions(self):
        return self._req("GET", f"{self.base}/v2/positions")

    def open_orders(self):
        return self._req("GET", f"{self.base}/v2/orders",
                         params={"status": "open", "nested": "false", "limit": 500})

    def asset(self, symbol):
        return self._req("GET", f"{self.base}/v2/assets/{symbol}")

    def portfolio_history(self, period="1M", timeframe="1D"):
        return self._req("GET", f"{self.base}/v2/account/portfolio/history",
                         params={"period": period, "timeframe": timeframe})

    # ---- Données ----
    def bars(self, symbols: list[str], days: int = 400) -> dict[str, list]:
        start = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)).date().isoformat()
        out: dict[str, list] = {}
        params = {"symbols": ",".join(symbols), "timeframe": "1Day", "start": start,
                  "limit": 10000, "feed": "iex", "adjustment": "all"}
        while True:
            data = self._req("GET", f"{self.DATA}/v2/stocks/bars", params=params)
            for sym, rows in (data.get("bars") or {}).items():
                out.setdefault(sym, []).extend(rows)
            token = data.get("next_page_token")
            if not token:
                return out
            params["page_token"] = token

    def snapshots(self, symbols: list[str]) -> dict:
        if not symbols:
            return {}
        return self._req("GET", f"{self.DATA}/v2/stocks/snapshots",
                         params={"symbols": ",".join(symbols), "feed": "iex"})

    def news(self, symbols: list[str] | None = None, limit: int = 20) -> list:
        params = {"limit": limit, "sort": "desc"}
        if symbols:
            params["symbols"] = ",".join(symbols)
        return self._req("GET", f"{self.DATA}/v1beta1/news", params=params).get("news", [])

    def movers(self, top: int = 15) -> dict:
        return self._req("GET", f"{self.DATA}/v1beta1/screener/stocks/movers", params={"top": top})

    def most_actives(self, top: int = 20) -> list:
        return self._req("GET", f"{self.DATA}/v1beta1/screener/stocks/most-actives",
                         params={"by": "volume", "top": top}).get("most_actives", [])

    # ---- Ordres ----
    def submit_bracket(self, symbol, qty: int, stop: float, take_profit: float, client_id: str | None = None):
        body = {
            "symbol": symbol, "qty": str(qty), "side": "buy", "type": "market",
            "time_in_force": "gtc", "order_class": "bracket",
            "take_profit": {"limit_price": _px(take_profit)},
            "stop_loss": {"stop_price": _px(stop)},
        }
        if client_id:
            body["client_order_id"] = client_id
        return self._req("POST", f"{self.base}/v2/orders", json=body)

    def submit_market_sell(self, symbol, qty: int, client_id: str | None = None):
        body = {"symbol": symbol, "qty": str(qty), "side": "sell", "type": "market", "time_in_force": "day"}
        if client_id:
            body["client_order_id"] = client_id
        return self._req("POST", f"{self.base}/v2/orders", json=body)

    def get_order(self, order_id):
        return self._req("GET", f"{self.base}/v2/orders/{order_id}", params={"nested": "true"})

    def latest_prices(self, symbols: list[str]) -> dict[str, float]:
        out = {}
        for i in range(0, len(symbols), 100):
            snaps = self.snapshots(symbols[i:i + 100])
            for s, snap in (snaps or {}).items():
                p = ((snap or {}).get("latestTrade") or {}).get("p") or ((snap or {}).get("dailyBar") or {}).get("c")
                if p:
                    out[s] = float(p)
        return out

    def submit_exits(self, symbol, qty: int, stop: float, take_profit: float | None):
        """Remet des ordres de sortie (OCO stop + TP, ou stop seul) sur une position existante."""
        if take_profit:
            body = {"symbol": symbol, "qty": str(qty), "side": "sell", "type": "limit",
                    "time_in_force": "gtc", "order_class": "oco",
                    "take_profit": {"limit_price": _px(take_profit)},
                    "stop_loss": {"stop_price": _px(stop)}}
        else:
            body = {"symbol": symbol, "qty": str(qty), "side": "sell", "type": "stop",
                    "time_in_force": "gtc", "stop_price": _px(stop)}
        return self._req("POST", f"{self.base}/v2/orders", json=body)

    def cancel_order(self, order_id):
        return self._req("DELETE", f"{self.base}/v2/orders/{order_id}")

    def replace_stop(self, order_id, stop: float):
        return self._req("PATCH", f"{self.base}/v2/orders/{order_id}", json={"stop_price": _px(stop)})

    def close_position(self, symbol, qty: int | None = None):
        params = {"qty": str(qty)} if qty else None
        return self._req("DELETE", f"{self.base}/v2/positions/{symbol}", params=params)
