"""Envoi des ordres validés à Alpaca (ventes d'abord pour libérer du cash, puis stops, puis achats)."""
import logging
import time

from .alpaca import AlpacaError

log = logging.getLogger("execution")
PRIORITY = {"vendre": 0, "alleger": 1, "ajuster_stop": 2, "acheter": 3}


def _cancel_exits(alpaca, ctx, sym):
    ex = ctx.exits.get(sym, {})
    for oid, _ in ex.get("stops", []) + ex.get("tps", []):
        try:
            alpaca.cancel_order(oid)
        except AlpacaError as e:
            log.warning("annulation %s : %s", oid, e)
    if ex.get("stops") or ex.get("tps"):
        time.sleep(2)  # l'annulation est asynchrone chez Alpaca


def _retry(fn, tries=3):
    for i in range(tries):
        try:
            return fn()
        except AlpacaError:
            if i == tries - 1:
                raise
            time.sleep(2)


def execute(alpaca, approved: list[dict], ctx, dry_run: bool) -> list[dict]:
    results = []
    for o in sorted(approved, key=lambda x: PRIORITY.get(x["action"], 9)):
        sym, action = o["symbole"], o["action"]
        res = {**o}
        try:
            if dry_run:
                res["statut"] = "simulé"
            elif action == "vendre":
                _cancel_exits(alpaca, ctx, sym)
                r = _retry(lambda: alpaca.close_position(sym))
                res.update(statut="envoyé", id=r.get("id"))
            elif action == "alleger":
                ex = ctx.exits.get(sym, {})
                stop = max((p for _, p in ex.get("stops", [])), default=None)
                tp = min((p for _, p in ex.get("tps", [])), default=None)
                _cancel_exits(alpaca, ctx, sym)
                r = _retry(lambda: alpaca.close_position(sym, qty=o["qty"]))
                res.update(statut="envoyé", id=r.get("id"))
                remaining = int(ctx.positions[sym]["qty"] - o["qty"])
                if stop and remaining >= 1:
                    time.sleep(2)
                    _retry(lambda: alpaca.submit_exits(sym, remaining, stop, tp))
                    res["sorties_remises"] = f"stop {stop} / TP {tp} sur {remaining} actions"
            elif action == "ajuster_stop":
                stops = ctx.exits.get(sym, {}).get("stops", [])
                if stops:
                    for oid, _ in stops:
                        alpaca.replace_stop(oid, o["stop_loss"])
                elif o["qty"] >= 1:
                    alpaca.submit_exits(sym, o["qty"], o["stop_loss"], None)
                res["statut"] = "envoyé"
            elif action == "acheter":
                r = alpaca.submit_bracket(sym, o["qty"], o["stop_loss"], o["take_profit"])
                res.update(statut="envoyé", id=r.get("id"))
        except AlpacaError as e:
            res.update(statut="erreur", erreur=str(e))
            log.error("%s %s : %s", action, sym, e)
        log.info("%s %s x%s -> %s", action, sym, o.get("qty"), res["statut"])
        results.append(res)
    return results
