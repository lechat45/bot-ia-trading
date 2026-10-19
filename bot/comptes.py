"""Un sous-compte par IA (comme les sous-comptes XTB d'Aywen).

Alpaca n'offre qu'un compte paper : ce registre (memoire/comptes.json) attribue chaque achat
à l'IA qui l'a décidé. Chaque position est faite de « lots » (un par achat) qui portent leurs
ordres de sortie Alpaca (stop loss et objectif de gain).
"""
import copy
import datetime as dt
import json
import logging
import threading
from pathlib import Path

from .alpaca import AlpacaError

log = logging.getLogger("comptes")
PATH = Path(__file__).resolve().parent.parent / "memoire" / "comptes.json"
DONE = ("filled",)
DEAD = ("canceled", "expired", "rejected", "done_for_day")


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


class Comptes:
    def __init__(self, data: dict, persist: bool):
        self.data = data
        self.persist = persist
        self.lock = threading.RLock()

    # ------------------------------------------------------------------ chargement
    @classmethod
    def load(cls, agent_ids: list[str], equity: float, persist: bool = True) -> "Comptes":
        if PATH.exists():
            data = json.loads(PATH.read_text(encoding="utf-8"))
        else:
            part = round(equity / len(agent_ids), 2)
            data = {"cree_le": _now(), "capital_total": round(equity, 2), "agents": {}}
            for a in agent_ids:
                data["agents"][a] = {"capital_depart": part, "cash": part, "positions": {},
                                     "realise": 0.0, "evenements": []}
            log.info("Registre du compte créé : %s $ (%s)", part, ", ".join(agent_ids))
        for a in agent_ids:  # une IA ajoutée plus tard démarre avec 0 $ (à financer à la main)
            data["agents"].setdefault(a, {"capital_depart": 0.0, "cash": 0.0, "positions": {},
                                          "realise": 0.0, "evenements": []})
        # En simulation, on travaille sur une copie : rien n'est enregistré.
        return cls(data if persist else copy.deepcopy(data), persist)

    def save(self):
        if self.persist:
            PATH.parent.mkdir(parents=True, exist_ok=True)
            PATH.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")

    def agent(self, aid: str) -> dict:
        return self.data["agents"][aid]

    def event(self, aid: str, texte: str):
        with self.lock:
            ev = self.agent(aid)["evenements"]
            ev.append({"ts": _now(), "texte": texte})
            del ev[:-25]

    def take_events(self, aid: str, since: str | None) -> list[str]:
        return [e["texte"] for e in self.agent(aid)["evenements"] if not since or e["ts"] > since]

    # ------------------------------------------------------------------ calculs
    @staticmethod
    def position_qty(pos: dict) -> int:
        return sum(l["qty"] for l in pos["lots"])

    def symbols(self) -> list[str]:
        return sorted({s for a in self.data["agents"].values() for s in a["positions"]})

    def valuation(self, aid: str, prices: dict) -> dict:
        a = self.agent(aid)
        rows, invested = [], 0.0
        for sym, pos in a["positions"].items():
            qty = self.position_qty(pos)
            if qty <= 0:
                continue
            cost = sum(l["qty"] * l["prix"] for l in pos["lots"])
            avg = cost / qty
            price = prices.get(sym) or avg
            val = qty * price
            invested += val
            stops = [l["stop"] for l in pos["lots"] if l.get("stop")]
            tps = [l["tp"] for l in pos["lots"] if l.get("tp")]
            rows.append({
                "symbole": sym, "qty": qty, "prix_achat": round(avg, 2), "prix": round(price, 2),
                "valeur": round(val, 2), "pl": round(val - cost, 2), "pl_pct": round((price / avg - 1) * 100, 2),
                "stop": max(stops) if stops else None, "tp": min(tps) if tps else None,
                "depuis": pos["lots"][0].get("date", "")[:10], "these": pos.get("these", "")[:300],
                "en_attente": any(l.get("statut") == "en_attente" for l in pos["lots"]),
            })
        value = a["cash"] + invested
        start = a["capital_depart"] or 1
        return {"cash": round(a["cash"], 2), "valeur": round(value, 2), "investi": round(invested, 2),
                "capital_depart": round(a["capital_depart"], 2), "pl": round(value - a["capital_depart"], 2),
                "pl_pct": round((value / start - 1) * 100, 2), "realise": round(a.get("realise", 0.0), 2),
                "positions": rows}

    # ------------------------------------------------------------------ registre
    def add_lot(self, aid, sym, lot: dict, these: str):
        with self.lock:
            a = self.agent(aid)
            pos = a["positions"].setdefault(sym, {"lots": [], "these": these})
            pos["these"] = these or pos.get("these", "")
            pos["lots"].append(lot)
            a["cash"] -= lot["qty"] * lot["prix"]

    def remove_qty(self, aid, sym, qty: int, price: float) -> float:
        """Retire qty actions (les plus anciennes d'abord) vendues à price. Renvoie la plus-value."""
        with self.lock:
            a = self.agent(aid)
            pos = a["positions"].get(sym)
            pl, left = 0.0, qty
            for lot in list(pos["lots"]):
                take = min(left, lot["qty"])
                pl += take * (price - lot["prix"])
                lot["qty"] -= take
                left -= take
                if lot["qty"] <= 0:
                    pos["lots"].remove(lot)
                if left <= 0:
                    break
            a["cash"] += qty * price
            a["realise"] = a.get("realise", 0.0) + pl
            if not pos["lots"]:
                del a["positions"][sym]
            return pl

    def reconcile(self, real: dict) -> list[str]:
        """Écarts entre les quantités du registre (lots exécutés) et les positions réelles Alpaca
        ({symbole: quantité}). Un achat encore en attente n'est pas compté."""
        mine: dict = {}
        for a in self.data["agents"].values():
            for sym, pos in a["positions"].items():
                mine[sym] = mine.get(sym, 0) + sum(l["qty"] for l in pos["lots"] if l.get("statut") != "en_attente")
        out = []
        for sym in sorted(set(mine) | set(real)):
            m, r = mine.get(sym, 0), real.get(sym, 0)
            if m != r:
                out.append(f"{sym} : {m} au registre, {r} chez Alpaca")
        return out

    # ------------------------------------------------------------------ synchronisation Alpaca
    @staticmethod
    def _follow(alpaca, order_id):
        """Suit un ordre, y compris s'il a été remplacé (stop remonté)."""
        o = alpaca.get_order(order_id)
        for _ in range(10):
            if o.get("status") == "replaced" and o.get("replaced_by"):
                o = alpaca.get_order(o["replaced_by"])
            else:
                break
        return o

    def sync(self, alpaca) -> None:
        """Met les sous-comptes à jour avec ce qui s'est passé chez Alpaca depuis la dernière séance."""
        with self.lock:
            for aid, a in self.data["agents"].items():
                for sym in list(a["positions"]):
                    for lot in list(a["positions"].get(sym, {}).get("lots", [])):
                        try:
                            self._sync_lot(alpaca, aid, sym, lot)
                        except AlpacaError as e:
                            log.warning("synchro %s %s : %s", aid, sym, e)

    def _sync_lot(self, alpaca, aid, sym, lot):
        a = self.agent(aid)
        if lot.get("statut") == "en_attente":
            o = alpaca.get_order(lot["parent_id"])
            if o.get("status") in DONE:
                price, qty = float(o["filled_avg_price"]), int(float(o["filled_qty"]))
                a["cash"] += lot["qty"] * lot["prix"] - qty * price  # on remplace la réservation
                lot.update(prix=price, qty=qty, statut="ouvert", **self.leg_ids(o))
                self.event(aid, f"Achat exécuté : {qty} {sym} à {price:.2f} $")
            elif o.get("status") in DEAD:
                a["cash"] += lot["qty"] * lot["prix"]
                a["positions"][sym]["lots"].remove(lot)
                if not a["positions"][sym]["lots"]:
                    del a["positions"][sym]
                self.event(aid, f"Achat de {sym} non exécuté (ordre {o.get('status')})")
            return
        for leg, label in (("stop_id", "Stop loss déclenché"), ("tp_id", "Objectif de gain atteint")):
            if not lot.get(leg):
                continue
            o = self._follow(alpaca, lot[leg])
            lot[leg] = o.get("id", lot[leg])
            if o.get("status") in DONE:
                price = float(o["filled_avg_price"])
                qty = lot["qty"]
                pl = self.remove_qty(aid, sym, qty, price)
                texte = f"{label} : {qty} {sym} vendues à {price:.2f} $ (plus-value {pl:+.2f} $)"
                self.event(aid, texte)
                if self.persist:  # trace dans l'historique des ordres (et notification)
                    from . import memory, notify

                    memory.append_journal([{"type": "execution", "ts": _now(), "agent": "alpaca", "action": "vendre",
                                            "symbole": sym, "qty": qty, "statut": "exécuté", "prix": price,
                                            "plus_value": round(pl, 2),
                                            "source": "stop loss" if leg == "stop_id" else "objectif de gain"}])
                    notify.send(f"{label} sur {sym}", texte, tags="chart_with_downwards_trend" if leg == "stop_id" else "tada")
                return

    @staticmethod
    def leg_ids(order: dict) -> dict:
        out = {"stop_id": None, "tp_id": None}
        for leg in order.get("legs") or []:
            if leg.get("type") in ("stop", "stop_limit"):
                out["stop_id"] = leg["id"]
            elif leg.get("type") == "limit":
                out["tp_id"] = leg["id"]
        return out
