"""Garde-fous codés en dur : chaque ordre décidé par les IA passe ici avant Alpaca.
Les IA ne peuvent pas contourner ces règles (elles reprennent les skills d'Aywen)."""
import datetime as dt
import math
import re
from dataclasses import dataclass, field

SYMBOL_RE = re.compile(r"^[A-Z]{1,5}(\.[A-Z])?$")


@dataclass
class Context:
    equity: float
    cash: float
    positions: dict  # sym -> {"qty": float, "avg": float, "price": float, "value": float}
    prices: dict  # sym -> dernier prix
    exits: dict  # sym -> {"stops": [(id, prix)], "tps": [(id, prix)]}
    journal: list = field(default_factory=list)  # exécutions récentes

    def current_stop(self, sym):
        stops = self.exits.get(sym, {}).get("stops", [])
        return max((p for _, p in stops), default=None)


def _executed(journal, sym, actions, since: dt.datetime):
    return any(e.get("type") == "execution" and e.get("symbole") == sym
               and e.get("action") in actions and e.get("statut") == "envoyé"
               and e.get("ts", "") >= since.isoformat() for e in journal)


def validate(orders: list[dict], ctx: Context, cfg) -> tuple[list[dict], list[dict]]:
    ok, rejected = [], []
    seen: set[str] = set()
    cash_left = ctx.cash
    cash_floor = ctx.equity * cfg.min_cash_pct / 100
    n_positions = len(ctx.positions)
    now = dt.datetime.now(dt.timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    for o in orders if isinstance(orders, list) else []:
        if not isinstance(o, dict):
            continue
        action = str(o.get("action", "")).lower().strip()
        sym = str(o.get("symbole", "")).upper().strip()

        def reject(reason):
            rejected.append({**o, "raison_rejet": reason})

        if len(ok) >= cfg.max_orders:
            reject(f"maximum {cfg.max_orders} ordres par session")
            continue
        if not SYMBOL_RE.match(sym):
            reject("symbole invalide")
            continue
        if sym in seen:
            reject("un seul ordre par titre et par session")
            continue
        price = ctx.prices.get(sym)

        if action in ("acheter", "renforcer"):
            if not price:
                reject("prix inconnu")
                continue
            if price < cfg.min_price:
                reject(f"prix < {cfg.min_price} $ (penny stock)")
                continue
            try:
                stop, tp = float(o["stop_loss"]), float(o["take_profit"])
            except (KeyError, TypeError, ValueError):
                reject("stop_loss et take_profit obligatoires")
                continue
            if not stop < price < tp:
                reject(f"il faut stop < prix ({price}) < take profit")
                continue
            dist = (price - stop) / price * 100
            if dist > cfg.max_stop_distance_pct:
                reject(f"stop trop loin ({dist:.1f} % > {cfg.max_stop_distance_pct} %)")
                continue
            if dist < cfg.min_stop_distance_pct:
                reject(f"stop trop proche ({dist:.1f} %), le bruit le déclencherait")
                continue
            rr = (tp - price) / (price - stop)
            if rr < cfg.min_reward_risk:
                reject(f"ratio gain/perte {rr:.2f} < {cfg.min_reward_risk}")
                continue
            if _executed(ctx.journal, sym, ("vendre", "alleger"), now - dt.timedelta(days=cfg.anti_churn_days)):
                reject(f"titre vendu il y a moins de {cfg.anti_churn_days} j (anti aller-retour)")
                continue
            held = sym in ctx.positions
            if not held and n_positions >= cfg.max_positions:
                reject(f"déjà {cfg.max_positions} positions")
                continue
            try:
                weight = float(o.get("poids_pct", 0))
            except (TypeError, ValueError):
                weight = 0
            weight = max(0.0, min(weight, cfg.max_position_pct))
            existing = ctx.positions.get(sym, {}).get("value", 0.0)
            amount = min(ctx.equity * weight / 100,
                         ctx.equity * cfg.max_position_pct / 100 - existing,
                         cash_left - cash_floor)
            qty = math.floor(amount / price) if amount > 0 else 0
            if qty < 1:
                reject("montant insuffisant (limite par ligne, cash minimum ou poids nul)")
                continue
            cash_left -= qty * price
            if not held:
                n_positions += 1
            ok.append({**o, "action": "acheter", "symbole": sym, "qty": qty,
                       "stop_loss": round(stop, 2), "take_profit": round(tp, 2),
                       "prix_ref": price, "montant": round(qty * price, 2)})

        elif action in ("vendre", "alleger"):
            pos = ctx.positions.get(sym)
            if not pos:
                reject("aucune position sur ce titre")
                continue
            if _executed(ctx.journal, sym, ("acheter",), today_start):
                reject("acheté aujourd'hui : pas d'aller-retour dans la journée")
                continue
            if action == "vendre":
                qty = pos["qty"]
            else:
                try:
                    pct = float(o.get("pourcentage", 50))
                except (TypeError, ValueError):
                    pct = 50
                qty = math.floor(pos["qty"] * max(10, min(pct, 90)) / 100)
                if qty < 1:
                    reject("position trop petite pour être allégée")
                    continue
            ok.append({**o, "action": action, "symbole": sym, "qty": qty})

        elif action == "ajuster_stop":
            pos = ctx.positions.get(sym)
            if not pos:
                reject("aucune position sur ce titre")
                continue
            try:
                new = float(o["stop_loss"])
            except (KeyError, TypeError, ValueError):
                reject("nouveau stop_loss manquant")
                continue
            cur = ctx.current_stop(sym)
            if cur is not None and new <= cur:
                reject(f"un stop ne se descend jamais (actuel {cur}, demandé {new})")
                continue
            if price and new >= price:
                reject("stop au-dessus du prix actuel")
                continue
            ok.append({**o, "action": action, "symbole": sym, "stop_loss": round(new, 2),
                       "qty": math.floor(pos["qty"])})
        else:
            reject(f"action inconnue « {action} »")
            continue
        seen.add(sym)
    return ok, rejected
