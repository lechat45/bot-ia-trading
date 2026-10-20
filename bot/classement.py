"""Classement des analystes : ce qu'auraient rapporté leurs idées d'achat depuis qu'ils les ont proposées
(au prix du jour de la proposition), qu'elles aient été achetées ou non, et la justesse des avis du
critique. Utilisé par le tableau de bord et donné à chaque IA au début de ses séances."""
import json

from . import memory


def load_propositions() -> list[dict]:
    """Propositions d'achat des séances réelles, une seule par analyste, titre et jour."""
    rows = list(memory.read_propositions())
    folder = memory.ROOT / "sessions"
    for p in sorted(folder.glob("*.json"), key=lambda p: p.stem) if folder.exists() else []:  # séances d'avant ce registre
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
            out.append(dict(r))
    return out


def compute(props: list[dict], prices: dict, analysts: list[str]) -> dict:
    if not props:
        return {"analystes": [], "propositions": 0}
    for p in props:
        px = prices.get(p["symbole"])
        p["rendement"] = round((px / p["prix_ref"] - 1) * 100, 2) if px else None
    mean = lambda xs: round(sum(xs) / len(xs), 2) if xs else None  # noqa: E731
    rows = []
    for aid in analysts:
        mine = [p for p in props if p.get("auteur") == aid and p["rendement"] is not None]
        r = [p["rendement"] for p in mine]
        best = max(mine, key=lambda p: p["rendement"], default=None)
        worst = min(mine, key=lambda p: p["rendement"], default=None)
        rows.append({"id": aid, "propositions": len(mine), "retenues": sum(1 for p in mine if p.get("retenue")),
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


MIN_IDEES = 5  # en dessous, les chiffres sont surtout du hasard : on le dit à l'IA
PETIT = " Échantillon encore trop petit pour en tirer des conclusions : continue d'appliquer ta méthode."


def _pct(v) -> str:
    if v is None:
        return "?"
    return f"{0.0 if abs(v) < 0.05 else v:+.1f} %".replace(".", ",").replace("+0,0", "0,0")


def summary(role: str, aid: str, data: dict, names: dict) -> str:
    """Quelques lignes pour l'ouverture de séance d'une IA : son propre bilan, ou celui de l'équipe."""
    rows = [r for r in data.get("analystes") or [] if r["propositions"]]
    if role == "analyste":
        r = next((x for x in rows if x["id"] == aid), None)
        if not r:
            return ""
        bought = (f"achetées par le gérant {_pct(r['moyenne_retenues'])}" if r["moyenne_retenues"] is not None
                  else "aucune achetée par le gérant")
        left = f", écartées {_pct(r['moyenne_ecartees'])}" if r["moyenne_ecartees"] is not None else ""
        txt = (f"{r['propositions']} idée(s) d'achat depuis le {data.get('depuis')} : rendement moyen {_pct(r['rendement_moyen'])}, "
               f"{r['reussite_pct']} % gagnantes ; {bought}{left} ; meilleure {r['meilleure']['symbole']} "
               f"{_pct(r['meilleure']['rendement'])}, pire {r['pire']['symbole']} {_pct(r['pire']['rendement'])}.")
        return (f"TON BILAN (ce qu'ont rapporté tes idées depuis que tu les as proposées) : {txt}"
                f"{PETIT if r['propositions'] < MIN_IDEES else ''}\n\n")
    if role == "critique":
        c = data.get("critique") or {}
        if not c.get("avis"):
            return ""
        return (f"TON BILAN : {c['justes_pct']} % de tes {c['avis']} avis « ok » ou « rejet » ont été confirmés par "
                f"l'évolution du cours depuis.{PETIT if c['avis'] < MIN_IDEES else ''}\n\n")
    if not rows:
        return ""
    ranking = " ; ".join(f"{names.get(r['id'], r['id'])} {_pct(r['rendement_moyen'])} ({r['propositions']} idées, "
                         f"{r['reussite_pct']} % gagnantes)" for r in rows)
    c = data.get("critique") or {}
    crit = f" Avis du critique confirmés : {c['justes_pct']} % ({c['avis']} avis)." if c.get("avis") else ""
    small = PETIT if sum(r["propositions"] for r in rows) < 3 * MIN_IDEES else ""
    return f"BILAN DES ANALYSTES (rendement moyen de leurs idées depuis leur proposition) : {ranking}.{crit}{small}\n\n"
