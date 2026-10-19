"""Passage des ordres chez Alpaca pour le sous-compte d'une IA (l'outil « Broker » d'Aywen).

Achat = ordre « bracket » : achat au marché + stop loss + objectif de gain automatiques.
En simulation, les ordres ne partent pas : ils sont « exécutés » au dernier prix connu,
sur une copie des sous-comptes qui n'est jamais enregistrée.
"""
import datetime as dt
import logging
import time
import uuid

from . import memory, notify
from .alpaca import AlpacaError
from .comptes import DEAD, DONE

log = logging.getLogger("broker")


def _now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


class Broker:
    def __init__(self, alpaca, comptes, dry_run: bool):
        self.alpaca, self.comptes, self.dry_run = alpaca, comptes, dry_run

    def price(self, sym) -> float | None:
        try:
            return self.alpaca.latest_prices([sym]).get(sym)
        except AlpacaError:
            return None

    def _wait(self, order_id, timeout=25):
        o = {}
        end = time.time() + timeout
        while time.time() < end:
            o = self.alpaca.get_order(order_id)
            if o.get("status") in DONE + DEAD:
                return o
            time.sleep(1.5)
        return o

    def _journal(self, aid, action, sym, qty, statut, **extra):
        if not self.dry_run:
            memory.append_journal([{"type": "execution", "ts": _now(), "agent": aid, "action": action,
                                    "symbole": sym, "qty": qty, "statut": statut, **extra}])

    # ------------------------------------------------------------------ achat
    def buy(self, aid, sym, qty, sl_pct, tp_pct, these="") -> dict:
        price = self.price(sym)
        if not price:
            return {"ok": False, "message": f"prix de {sym} indisponible"}
        stop, tp = round(price * (1 - sl_pct / 100), 2), round(price * (1 + tp_pct / 100), 2)
        if self.dry_run:
            self.comptes.add_lot(aid, sym, {"qty": qty, "prix": price, "date": _now(), "stop": stop, "tp": tp,
                                            "statut": "ouvert", "parent_id": "simulation"}, these)
            return {"ok": True, "message": f"SIMULATION : achat de {qty} {sym} à {price:.2f} $ "
                    f"(stop {stop:.2f} $, objectif {tp:.2f} $)", "qty": qty, "prix": price, "stop": stop, "tp": tp}
        try:
            o = self.alpaca.submit_bracket(sym, qty, stop, tp, client_id=f"{aid}-{sym}-{uuid.uuid4().hex[:8]}")
            o = self._wait(o["id"])
        except AlpacaError as e:
            self._journal(aid, "acheter", sym, qty, "erreur", erreur=str(e)[:200])
            return {"ok": False, "message": f"Alpaca a refusé l'ordre : {e}"}
        status = o.get("status")
        if status in DONE:
            fill, filled = float(o["filled_avg_price"]), int(float(o["filled_qty"]))
            lot = {"qty": filled, "prix": fill, "date": _now(), "stop": stop, "tp": tp, "statut": "ouvert",
                   "parent_id": o["id"], **self.comptes.leg_ids(o)}
            self.comptes.add_lot(aid, sym, lot, these)
            self._journal(aid, "acheter", sym, filled, "exécuté", prix=fill, stop=stop, tp=tp)
            notify.send(f"Achat : {filled} {sym}", f"{filled} {sym} achetées à {fill:.2f} $ (stop {stop:.2f} $, "
                        f"objectif {tp:.2f} $), soit {filled * fill:,.0f} $.".replace(",", " "))
            return {"ok": True, "message": f"Achat exécuté : {filled} {sym} à {fill:.2f} $ "
                    f"(stop {stop:.2f} $, objectif {tp:.2f} $)", "qty": filled, "prix": fill, "stop": stop, "tp": tp}
        if status in DEAD:
            self._journal(aid, "acheter", sym, qty, "erreur", erreur=status)
            return {"ok": False, "message": f"ordre {status} par Alpaca"}
        # Pas encore exécuté (marché fermé ou lent) : on réserve le cash, la synchro finira le travail.
        self.comptes.add_lot(aid, sym, {"qty": qty, "prix": price, "date": _now(), "stop": stop, "tp": tp,
                                        "statut": "en_attente", "parent_id": o["id"]}, these)
        self._journal(aid, "acheter", sym, qty, "envoyé")
        return {"ok": True, "message": f"Ordre d'achat de {qty} {sym} envoyé, en attente d'exécution",
                "qty": qty, "prix": price, "stop": stop, "tp": tp}

    # ------------------------------------------------------------------ vente
    def sell(self, aid, sym, qty, raison="") -> dict:
        pos = self.comptes.agent(aid)["positions"].get(sym)
        if not pos:
            return {"ok": False, "message": f"pas de position {sym}"}
        total = self.comptes.position_qty(pos)
        stops = [l["stop"] for l in pos["lots"] if l.get("stop")]
        tps = [l["tp"] for l in pos["lots"] if l.get("tp")]
        if self.dry_run:
            price = self.price(sym) or pos["lots"][0]["prix"]
            pl = self.comptes.remove_qty(aid, sym, qty, price)
            return {"ok": True, "message": f"SIMULATION : vente de {qty} {sym} à {price:.2f} $ "
                    f"(plus-value {pl:+.2f} $)", "qty": qty, "prix": price}
        # 1. annuler les ordres de sortie de cette IA sur ce titre
        for lot in pos["lots"]:
            for leg in ("stop_id", "tp_id"):
                if lot.get(leg):
                    try:
                        self.alpaca.cancel_order(lot[leg])
                    except AlpacaError as e:
                        log.info("annulation %s : %s", lot[leg], e)
        for lot in pos["lots"]:
            for leg in ("stop_id", "tp_id"):
                if lot.get(leg):
                    o = self._wait(lot[leg], timeout=10)
                    if o.get("status") in DONE:  # le stop s'est déclenché entre-temps
                        self.comptes.sync(self.alpaca)
                        return {"ok": False, "message": "la position vient d'être vendue par son stop ou son objectif"}
        # 2. vendre
        try:
            o = self.alpaca.submit_market_sell(sym, qty, client_id=f"{aid}-{sym}-v-{uuid.uuid4().hex[:8]}")
            o = self._wait(o["id"])
        except AlpacaError as e:
            self._journal(aid, "vendre", sym, qty, "erreur", erreur=str(e)[:200])
            self._rearm(aid, sym, total, stops, tps)
            return {"ok": False, "message": f"Alpaca a refusé la vente : {e}"}
        if o.get("status") not in DONE:
            self._journal(aid, "vendre", sym, qty, "erreur", erreur=o.get("status"))
            return {"ok": False, "message": f"vente non exécutée ({o.get('status')})"}
        price = float(o["filled_avg_price"])
        pl = self.comptes.remove_qty(aid, sym, qty, price)
        self._journal(aid, "vendre" if qty >= total else "alleger", sym, qty, "exécuté", prix=price,
                      plus_value=round(pl, 2), raison=raison[:200])
        notify.send(f"Vente : {qty} {sym}", f"{qty} {sym} vendues à {price:.2f} $, plus-value {pl:+.2f} $.",
                    tags="moneybag")
        # 3. remettre la protection sur ce qui reste
        if total - qty >= 1 and stops:
            self._rearm(aid, sym, total - qty, stops, tps)
        return {"ok": True, "message": f"Vente exécutée : {qty} {sym} à {price:.2f} $ (plus-value {pl:+.2f} $)",
                "qty": qty, "prix": price}

    def _rearm(self, aid, sym, qty, stops, tps):
        pos = self.comptes.agent(aid)["positions"].get(sym)
        if not pos or not stops:
            return
        stop, tp = max(stops), (min(tps) if tps else None)
        try:
            o = self.alpaca.submit_exits(sym, qty, stop, tp)
            o = self.alpaca.get_order(o["id"])
            ids = {"stop_id": None, "tp_id": None}
            if o.get("type") in ("stop", "stop_limit"):
                ids["stop_id"] = o["id"]
            else:
                ids["tp_id"] = o["id"]
                ids.update({k: v for k, v in self.comptes.leg_ids(o).items() if v})
            with self.comptes.lock:
                cost = sum(l["qty"] * l["prix"] for l in pos["lots"])
                n = self.comptes.position_qty(pos)
                pos["lots"] = [{"qty": n, "prix": cost / n, "date": pos["lots"][0]["date"], "stop": stop, "tp": tp,
                                "statut": "ouvert", "parent_id": o["id"], **ids}]
        except AlpacaError as e:
            log.error("impossible de remettre la protection sur %s : %s", sym, e)
            self.comptes.event(aid, f"ATTENTION : {sym} n'a plus de stop loss ({e})")

    # ------------------------------------------------------------------ stop
    def adjust_stop(self, aid, sym, new_stop) -> dict:
        pos = self.comptes.agent(aid)["positions"].get(sym)
        if not pos:
            return {"ok": False, "message": f"pas de position {sym}"}
        if self.dry_run:
            for lot in pos["lots"]:
                lot["stop"] = new_stop
            return {"ok": True, "message": f"SIMULATION : stop de {sym} remonté à {new_stop:.2f} $"}
        done = 0
        for lot in pos["lots"]:
            if not lot.get("stop_id"):
                continue
            try:
                o = self.alpaca.replace_stop(lot["stop_id"], new_stop)
                lot["stop_id"], lot["stop"] = o.get("id", lot["stop_id"]), new_stop
                done += 1
            except AlpacaError as e:
                return {"ok": False, "message": f"Alpaca a refusé la modification : {e}"}
        if not done:
            return {"ok": False, "message": "aucun stop modifiable sur cette position"}
        self._journal(aid, "ajuster_stop", sym, None, "exécuté", stop=new_stop)
        return {"ok": True, "message": f"Stop de {sym} remonté à {new_stop:.2f} $"}
