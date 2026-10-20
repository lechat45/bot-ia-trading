"""Ce que valent les critères du screener, mesuré sur le passé.

Chaque critère est rejoué sur 3 ans de cours des grandes valeurs de l'univers : une fois par semaine,
on prend les 10 actions qu'il aurait signalées, et on mesure ce qu'elles ont rapporté 5, 20 et 60
séances plus tard, comparé au S&P 500 sur les mêmes périodes. Aucun appel d'IA : tout est calculé par
le code. Limites à garder en tête : un passé ne prédit pas l'avenir, l'univers ne contient que les
grandes entreprises d'aujourd'hui (celles qui ont disparu manquent) et les frais ne sont pas comptés.
"""
import datetime as dt
import statistics

from . import tools

HORIZONS = (5, 20, 60)
STEP = 5  # un jour testé par semaine : des signaux moins redondants
PICKS = 10  # comme le screener (10 résultats par défaut)


def _series(bars: list[dict]) -> list[dict | None]:
    """Les indicateurs du screener pour chaque séance, calculés en un seul passage."""
    c = [b["c"] for b in bars]
    v = [b.get("v") or 0 for b in bars]
    n = len(c)
    pre = [0.0]
    for x in c:
        pre.append(pre[-1] + x)
    out: list[dict | None] = [None] * n
    for i in range(252, n):
        gains = sum(max(c[j] - c[j - 1], 0) for j in range(i - 13, i + 1))
        losses = sum(max(c[j - 1] - c[j], 0) for j in range(i - 13, i + 1))
        vol20 = sum(v[i - 19:i + 1]) / 20
        out[i] = {
            "prix": c[i], "sma50": (pre[i + 1] - pre[i - 49]) / 50, "sma200": (pre[i + 1] - pre[i - 199]) / 200,
            "perf_1j_pct": (c[i] / c[i - 1] - 1) * 100, "perf_5j_pct": (c[i] / c[i - 5] - 1) * 100,
            "perf_1m_pct": (c[i] / c[i - 21] - 1) * 100, "perf_3m_pct": (c[i] / c[i - 63] - 1) * 100,
            "rsi14": 100.0 if losses == 0 else 100 - 100 / (1 + gains / losses),
            "ecart_plus_haut_pct": (c[i] / max(c[i - 251:i + 1]) - 1) * 100,
            "volume_vs_moy20": v[i] / vol20 if vol20 else None,
        }
    return out


def _picks(critere: str, day: dict) -> list[str]:
    """Les actions qu'aurait signalées un critère ce jour-là ({symbole: indicateurs})."""
    if critere in tools.STRATEGY_SCREENS:
        keep, key, desc = tools.STRATEGY_SCREENS[critere]
        rows = [(s, i) for s, i in day.items() if keep(i)]
    else:
        key, desc = tools.SCREENS[critere]
        rows = [(s, i) for s, i in day.items() if i.get(key) is not None]
    rows.sort(key=lambda r: r[1][key], reverse=desc)
    return [s for s, _ in rows[:PICKS]]


def _stats(rets: list[float], spy: list[float]) -> dict:
    if not rets:
        return {"signaux": 0}
    m = statistics.fmean(rets)
    out = {"signaux": len(rets), "moyenne_pct": round(m, 2), "mediane_pct": round(statistics.median(rets), 2),
           "gagnants_pct": round(100 * sum(r > 0 for r in rets) / len(rets))}
    if spy:
        out["sp500_pct"] = round(statistics.fmean(spy), 2)
        out["ecart_points"] = round(m - out["sp500_pct"], 2)
    return out


def run(bars_by_sym: dict, spy_bars: list[dict]) -> dict:
    """Rejoue tous les critères du screener. bars_by_sym : {symbole: cours quotidiens (3 ans de préférence)}."""
    dates = {str(b["t"])[:10]: k for k, b in enumerate(spy_bars)}
    spy_c = [b["c"] for b in spy_bars]
    series = {}
    for sym, bars in bars_by_sym.items():
        if len(bars) >= 252 + max(HORIZONS) + STEP:
            series[sym] = ([str(b["t"])[:10] for b in bars], [b["c"] for b in bars], _series(bars))
    if not series or not spy_bars:
        return {}
    # jours testés : ceux du S&P 500, une fois par semaine, en laissant 60 séances pour mesurer la suite
    test_days = [d for d, k in dates.items() if 252 <= k < len(spy_c) - max(HORIZONS)][::STEP]
    criteres = list(tools.STRATEGY_SCREENS) + list(tools.SCREENS)
    acc = {c: {h: ([], []) for h in HORIZONS} for c in criteres}
    for d in test_days:
        k = dates[d]
        day, fwd = {}, {}
        for sym, (ds, cs, ind) in series.items():
            try:
                i = ds.index(d)
            except ValueError:
                continue
            if ind[i] is None or i + max(HORIZONS) >= len(cs):
                continue
            day[sym] = ind[i]
            fwd[sym] = {h: (cs[i + h] / cs[i] - 1) * 100 for h in HORIZONS}
        if len(day) < 50:
            continue
        spy_fwd = {h: (spy_c[k + h] / spy_c[k] - 1) * 100 for h in HORIZONS}
        for crit in criteres:
            for sym in _picks(crit, day):
                for h in HORIZONS:
                    acc[crit][h][0].append(fwd[sym][h])
                    acc[crit][h][1].append(spy_fwd[h])
    return {
        "periode": f"{test_days[0]} au {test_days[-1]}" if test_days else "",
        "jours_testes": len(test_days), "valeurs": len(series),
        "calcule_le": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "criteres": {c: {f"{h}j": _stats(*acc[c][h]) for h in HORIZONS} for c in criteres},
        "limites": "passé ≠ avenir ; univers des grandes valeurs d'aujourd'hui ; frais non comptés",
    }


def summary(data: dict, criteres=tuple(tools.STRATEGY_SCREENS)) -> str:
    """Une ligne par critère, pour l'ouverture de séance des IA (horizon 20 séances)."""
    rows = []
    for c in criteres:
        s = (data.get("criteres") or {}).get(c, {}).get("20j") or {}
        if s.get("signaux"):
            rows.append(f"{c} {s['moyenne_pct']:+.1f} % à 20 séances (S&P 500 {s.get('sp500_pct', 0):+.1f} %), "
                        f"{s['gagnants_pct']} % gagnants".replace(".", ","))
    if not rows:
        return ""
    return (f"CE QUE VALENT TES CRITÈRES DE SCREENER, testés sur le passé ({data.get('periode')}, "
            f"{data.get('valeurs')} grandes valeurs ; passé ≠ avenir) : " + " ; ".join(rows) + ".\n\n")
