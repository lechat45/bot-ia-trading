"""Garde-fous codés en dur, appliqués au sous-compte de chaque IA avant tout ordre.

Ils reprennent les règles des skills d'Aywen (stop obligatoire et jamais abaissé, taille de
position limitée, pas d'aller-retour…). L'IA ne peut pas les contourner : un ordre refusé lui
est renvoyé avec la raison, pour qu'elle corrige si elle le souhaite.
"""
import datetime as dt
import math
import re

SYMBOL_RE = re.compile(r"^[A-Z]{1,5}(\.[A-Z])?$")


def clean_symbol(s) -> str:
    return str(s or "").upper().strip().lstrip("$")


def _num(v, default=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _done(journal, aid, sym, actions, since: dt.datetime) -> bool:
    return any(e.get("type") == "execution" and e.get("agent") == aid and e.get("symbole") == sym
               and e.get("action") in actions and e.get("statut") in ("exécuté", "envoyé")
               and e.get("ts", "") >= since.isoformat() for e in journal)


def check_buy(cfg, aid, val: dict, sym: str, price: float | None, montant, sl_pct, tp_pct,
              journal: list, reserved: float = 0.0, clamp: bool = False):
    """Renvoie (ok, message, détails). clamp=True réduit le montant aux limites au lieu de refuser
    (utilisé à l'ouverture, quand le prix a un peu bougé depuis le matin)."""
    if not SYMBOL_RE.match(sym):
        return False, f"symbole « {sym} » invalide", {}
    if not price:
        return False, f"prix de {sym} introuvable (titre non coté aux États-Unis ?)", {}
    if price < cfg.min_price:
        return False, f"prix {price:.2f} $ < {cfg.min_price:g} $ : penny stock interdit", {}
    sl, tp, amount = _num(sl_pct), _num(tp_pct), _num(montant)
    if sl is None or tp is None:
        return False, "stop_loss_pct et take_profit_pct sont obligatoires", {}
    if not cfg.min_stop_distance_pct <= sl <= cfg.max_stop_distance_pct:
        return False, (f"stop_loss_pct doit être entre {cfg.min_stop_distance_pct:g} et "
                       f"{cfg.max_stop_distance_pct:g} % (reçu {sl:g})"), {}
    if tp <= 0 or tp / sl < cfg.min_reward_risk:
        return False, (f"ratio gain/perte {tp / sl if sl else 0:.2f} < {cfg.min_reward_risk:g} : "
                       f"take_profit_pct doit valoir au moins {sl * cfg.min_reward_risk:.1f}"), {}
    now = dt.datetime.now(dt.timezone.utc)
    if _done(journal, aid, sym, ("vendre", "alleger"), now - dt.timedelta(days=cfg.anti_churn_days)):
        return False, f"{sym} vendu il y a moins de {cfg.anti_churn_days} jours : pas d'aller-retour", {}
    positions = {p["symbole"]: p for p in val["positions"]}
    if sym not in positions and len(positions) >= cfg.max_positions:
        return False, f"déjà {cfg.max_positions} positions : vendez-en une avant d'en ouvrir une autre", {}
    existing = positions.get(sym, {}).get("valeur", 0.0)
    max_line = val["valeur"] * cfg.max_position_pct / 100 - existing
    cash_free = val["cash"] - reserved - val["valeur"] * cfg.min_cash_pct / 100
    limit = min(max_line, cash_free)
    if amount is None or amount <= 0:
        return False, f"montant_usd manquant (maximum possible : {max(0, limit):.0f} $)", {}
    if amount > limit + 0.01:
        if not clamp:
            why = "limite par titre" if max_line < cash_free else "liquidités disponibles (après réserve et ordres planifiés)"
            return False, f"montant trop élevé : maximum {max(0, limit):.0f} $ ({why})", {}
        amount = limit
    qty = math.floor(amount / price) if amount > 0 else 0
    if qty < 1:
        return False, f"montant insuffisant pour acheter 1 action à {price:.2f} $", {}
    return True, "ok", {"qty": qty, "montant": round(qty * price, 2), "prix_ref": round(price, 2),
                        "stop": round(price * (1 - sl / 100), 2), "tp": round(price * (1 + tp / 100), 2),
                        "stop_loss_pct": sl, "take_profit_pct": tp}


def check_sell(cfg, aid, val: dict, sym: str, pourcentage, journal: list):
    positions = {p["symbole"]: p for p in val["positions"]}
    pos = positions.get(sym)
    if not pos:
        return False, f"vous ne détenez pas {sym}", {}
    if pos.get("en_attente"):
        return False, f"l'achat de {sym} n'est pas encore exécuté", {}
    today = dt.datetime.now(dt.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    if _done(journal, aid, sym, ("acheter",), today):
        return False, f"{sym} acheté aujourd'hui : pas d'aller-retour dans la journée", {}
    pct = _num(pourcentage, 100.0)
    pct = max(1.0, min(100.0, pct))
    qty = pos["qty"] if pct >= 100 else math.floor(pos["qty"] * pct / 100)
    if qty < 1:
        return False, "quantité à vendre nulle", {}
    return True, "ok", {"qty": qty, "pourcentage": pct}


def check_stop(cfg, val: dict, sym: str, new_stop, price: float | None):
    positions = {p["symbole"]: p for p in val["positions"]}
    pos = positions.get(sym)
    if not pos:
        return False, f"vous ne détenez pas {sym}", {}
    if pos.get("en_attente"):
        return False, f"l'achat de {sym} n'est pas encore exécuté", {}
    new = _num(new_stop)
    if new is None or new <= 0:
        return False, "nouveau_stop invalide", {}
    cur = pos.get("stop")
    if cur is not None and new <= cur:
        return False, f"un stop ne se descend jamais (actuel {cur:.2f} $, demandé {new:.2f} $)", {}
    if price and new >= price:
        return False, f"le stop doit rester sous le prix actuel ({price:.2f} $)", {}
    return True, "ok", {"stop": round(new, 2)}
