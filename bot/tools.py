"""Outils d'analyse (équivalents gratuits de ceux d'Aywen) : indicateurs graphiques,
données fondamentales (yfinance) et sentiment Reddit. Tout est calculé par le code
pour éviter les erreurs de calcul des IA (dates, pourcentages)."""
import datetime as dt
import logging
import math
import statistics

import requests

log = logging.getLogger("outils")


def _r(x, n=2):
    return None if x is None else round(x, n)


def indicators(bars: list[dict]) -> dict:
    closes = [b["c"] for b in bars]
    if len(closes) < 20:
        return {"historique": "insuffisant"}
    highs, lows, vols = [b["h"] for b in bars], [b["l"] for b in bars], [b["v"] for b in bars]
    last = closes[-1]

    def sma(n):
        return _r(sum(closes[-n:]) / n) if len(closes) >= n else None

    def perf(n):
        return _r((last / closes[-n - 1] - 1) * 100, 1) if len(closes) > n else None

    gains = [max(closes[i] - closes[i - 1], 0) for i in range(len(closes) - 14, len(closes))]
    losses = [max(closes[i - 1] - closes[i], 0) for i in range(len(closes) - 14, len(closes))]
    avg_loss = sum(losses) / 14
    rsi = 100.0 if avg_loss == 0 else 100 - 100 / (1 + (sum(gains) / 14) / avg_loss)
    trs = [max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
           for i in range(len(closes) - 14, len(closes))]
    rets = [closes[i] / closes[i - 1] - 1 for i in range(len(closes) - 20, len(closes))]
    year = closes[-252:]
    vol20 = sum(vols[-20:]) / 20
    return {
        "prix": _r(last),
        "sma20": sma(20), "sma50": sma(50), "sma200": sma(200),
        "perf_5j_pct": perf(5), "perf_1m_pct": perf(21), "perf_3m_pct": perf(63),
        "perf_1an_pct": perf(252),
        "rsi14": _r(rsi, 0),
        "atr14": _r(sum(trs) / 14),
        "volat_annuelle_pct": _r(statistics.pstdev(rets) * math.sqrt(252) * 100, 0),
        "plus_haut_52s": _r(max(year)), "plus_bas_52s": _r(min(year)),
        "ecart_plus_haut_pct": _r((last / max(year) - 1) * 100, 1),
        "volume_vs_moy20": _r(vols[-1] / vol20, 1) if vol20 else None,
    }


def _big(x):
    if x is None:
        return None
    for unit, div in (("T", 1e12), ("Md", 1e9), ("M", 1e6)):
        if abs(x) >= div:
            return f"{x / div:.1f}{unit}"
    return f"{x:.0f}"


def fundamentals(symbol: str, today: dt.date) -> dict | None:
    try:
        import yfinance as yf

        t = yf.Ticker(symbol)
        info = t.info or {}

        def pct(key):
            v = info.get(key)
            return _r(v * 100, 1) if isinstance(v, (int, float)) else None

        out = {
            "nom": info.get("shortName"),
            "secteur": info.get("sector"),
            "industrie": info.get("industry"),
            "capitalisation": _big(info.get("marketCap")),
            "per": _r(info.get("trailingPE"), 1),
            "per_attendu": _r(info.get("forwardPE"), 1),
            "prix_sur_actif": _r(info.get("priceToBook"), 1),
            "marge_nette_pct": pct("profitMargins"),
            "marge_op_pct": pct("operatingMargins"),
            "croissance_ca_pct": pct("revenueGrowth"),
            "croissance_benef_pct": pct("earningsGrowth"),
            "roe_pct": pct("returnOnEquity"),
            "dette_sur_fp": _r(info.get("debtToEquity"), 0),
            "flux_tresorerie_libre": _big(info.get("freeCashflow")),
            "rendement_dividende_pct": _r(info.get("dividendYield"), 2),
            "objectif_analystes": _r(info.get("targetMeanPrice")),
            "avis_analystes": info.get("recommendationKey"),
        }
        try:
            cal = t.calendar or {}
            dates = cal.get("Earnings Date") if isinstance(cal, dict) else None
            if dates:
                d = dates[0] if isinstance(dates, list) else dates
                d = d.date() if isinstance(d, dt.datetime) else d
                out["prochains_resultats"] = d.isoformat()
                out["jours_avant_resultats"] = (d - today).days
        except Exception:  # le calendrier yfinance est souvent incomplet
            pass
        if "prochains_resultats" not in out:
            out["prochains_resultats"] = "inconnue"
        return {k: v for k, v in out.items() if v is not None}
    except Exception as e:
        log.info("fondamentaux %s indisponibles : %s", symbol, e)
        return None


_REDDIT: dict | None = None


def reddit_trending() -> dict:
    """Mentions Reddit des dernières 24 h (r/wallstreetbets, r/stocks…) via ApeWisdom, gratuit et sans clé."""
    global _REDDIT
    if _REDDIT is None:
        _REDDIT = {}
        try:
            for page in (1, 2, 3):
                r = requests.get(f"https://apewisdom.io/api/v1.0/filter/all-stocks/page/{page}", timeout=15)
                if r.status_code != 200:
                    break
                for x in r.json().get("results", []):
                    _REDDIT[x["ticker"]] = x
        except Exception as e:
            log.info("tendances Reddit indisponibles : %s", e)
    return _REDDIT


def reddit_sentiment(symbol: str) -> dict | None:
    data = reddit_trending()
    if not data:
        return None
    x = data.get(symbol)
    if not x:
        return {"mentions_24h": "hors du top 300 (peu discuté)"}
    return {"rang": x.get("rank"), "mentions_24h": x.get("mentions"),
            "mentions_veille": x.get("mentions_24h_ago"), "rang_veille": x.get("rank_24h_ago"),
            "upvotes": x.get("upvotes")}
