"""Tests des données calculées pour les IA (sans réseau). Lancer : python tests/test_donnees.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot import classement, tools  # noqa: E402


def test_concurrents_meme_industrie_puis_secteur():
    unh = tools.peers("UNH", "Healthcare", "Healthcare Plans")
    assert unh[:2] == ["CVS", "ELV"] or set(unh[:2]) == {"CVS", "ELV"}  # même industrie d'abord
    assert len(unh) == 4 and "UNH" not in unh
    assert tools.peers("XXXX", None, None) == []


def test_comparaison_aux_concurrents():
    f = {"industrie": "A", "per_attendu": 15.0, "marge_op_pct": 20.0}
    comp = tools.peer_comparison(f, {"P1": {"industrie": "A", "per_attendu": 20.0, "marge_op_pct": 10.0},
                                     "P2": {"industrie": "B", "per_attendu": 24.0, "marge_op_pct": 12.0}, "P3": None})
    assert comp["mediane"]["per_attendu"] == 22.0 and [r["lien"] for r in comp["concurrents"]] == ["industrie", "secteur"]
    assert "PER attendu 15 contre 22" in comp["lecture"]


def test_niveaux_et_stops_calcules():
    bars = [{"o": 100, "h": 101 + i % 3, "l": 98 - i % 2, "c": 100 + (i % 5) * 0.5, "v": 1000} for i in range(60)]
    lv = tools.levels(bars, 102.0)
    assert lv["plus_bas_20j"] == 97 and lv["atr_pct"] > 0
    for s in lv["stops_possibles"].values():
        assert 1 <= s["stop_loss_pct"] <= 15 and s["prix"] < 102
    assert tools.levels(bars[:5], 102.0) == {}


def _serie(closes):
    return [{"o": c, "h": c * 1.01, "l": c * 0.99, "c": c, "v": 1000} for c in closes]


def test_criteres_du_screener_par_strategie():
    hausse = [100 + i * 0.5 for i in range(250)]
    repli = hausse + [hausse[-1] - i * 1.2 for i in range(1, 7)]  # tendance intacte, petit repli de 6 jours
    chute = [100.0] * 200 + [100 - i * 1.5 for i in range(1, 21)] + [70 + i * 1.5 for i in range(1, 6)]  # RSI ~36
    bars = {"REPLI": _serie(repli), "HAUSSE": _serie(hausse), "CHUTE": _serie(chute)}
    assert [r["s"] for r in tools.screen_strategy(bars, "repli_dans_tendance", 5)] == ["REPLI"]
    assert "HAUSSE" in [r["s"] for r in tools.screen_strategy(bars, "tendance_haussiere", 5)]
    assert [r["s"] for r in tools.screen_strategy(bars, "rebond_apres_chute", 5)] == ["CHUTE"]


def test_elan_12_mois_et_faible_volatilite():
    import datetime as dt
    from bot import backtest

    def serie(f):
        start = dt.date(2025, 1, 1)
        return [{"t": (start + dt.timedelta(days=i)).isoformat(), "o": f(i), "h": f(i) * 1.01, "l": f(i) * 0.99,
                 "c": f(i), "v": 1000} for i in range(300)]
    bars = {"FORT": serie(lambda i: 100 * 1.004 ** min(i, 278)),  # forte hausse sur un an, plat le dernier mois
            "CALME": serie(lambda i: 100 * 1.0005 ** i * (1 + 0.002 * (-1) ** i)),
            "AGITE": serie(lambda i: 100 * 1.001 ** i * (1 + 0.03 * (-1) ** i))}
    assert tools.screen_strategy(bars, "momentum_12_1", 3)[0]["s"] == "FORT"
    assert [r["s"] for r in tools.screen_strategy(bars, "faible_volatilite", 3)][0] in ("CALME", "FORT")
    assert tools.screen_strategy(bars, "faible_volatilite", 3)[-1]["s"] == "AGITE"
    ind, ser = tools.indicators(bars["AGITE"]), backtest._series(bars["AGITE"])[-1]  # même calcul partout
    assert abs(ind["perf_12_1_pct"] - ser["perf_12_1_pct"]) < 0.1 and abs(ind["volat_1an_pct"] - ser["volat_1an_pct"]) < 0.1


def test_filtre_de_tendance_10_mois():
    import datetime as dt

    def mois(closes):
        return [{"t": f"2025-{m:02d}-28" if m <= 12 else f"2026-{m - 12:02d}-28", "c": c} for m, c in enumerate(closes, 1)]
    hausse = tools.trend_filter(mois([100 + 5 * k for k in range(12)] + [200]), dt.date(2026, 1, 15))
    assert hausse["haussiere"] and hausse["mois"] == "décembre" and hausse["moyenne_10_mois"] == 132.5
    baisse = tools.trend_filter(mois([150 - 4 * k for k in range(12)]), dt.date(2026, 1, 15))
    assert not baisse["haussiere"] and baisse["ecart_pct"] < 0
    assert tools.trend_filter(mois([100] * 5), dt.date(2026, 1, 15)) is None  # pas assez d'historique


def test_taille_divisee_par_2_en_tendance_baissiere():
    from types import SimpleNamespace
    from bot.risk import check_buy

    cfg = SimpleNamespace(earnings_blackout_days=1, min_price=5, min_stop_distance_pct=2, max_stop_distance_pct=15,
                          min_reward_risk=1.5, anti_churn_days=5, max_positions=10, max_position_pct=15,
                          min_cash_pct=5, max_sector_pct=35)
    val = {"valeur": 100_000, "cash": 100_000, "positions": []}
    ok, _, d = check_buy(cfg, "t", val, "AAPL", 100, 15_000, 5, 10, [])
    assert ok and d["qty"] == 150
    ok, msg, _ = check_buy(cfg, "t", val, "AAPL", 100, 15_000, 5, 10, [], tendance_baissiere=True)
    assert not ok and "7.5 %" in msg.replace(",", ".") and "baissière" in msg
    ok, _, d = check_buy(cfg, "t", val, "AAPL", 100, 15_000, 5, 10, [], clamp=True, tendance_baissiere=True)
    assert ok and d["qty"] == 75


def test_risque_du_portefeuille():
    import datetime as dt
    val = {"valeur": 100_000, "positions": [
        {"symbole": "AAA", "qty": 10, "prix": 100.0, "stop": 94.0, "tp": 112.0, "valeur": 1000.0, "depuis": "2026-10-10"},
        {"symbole": "BBB", "qty": 20, "prix": 50.0, "stop": 45.0, "tp": None, "valeur": 1000.0, "depuis": "2026-10-19"}]}
    r = tools.portfolio_risk(val, {"AAA": "Santé", "BBB": "Santé"}.get, today=dt.date(2026, 10, 20))
    a = r["positions"][0]
    assert a["distance_stop_pct"] == 6.0 and a["distance_objectif_pct"] == 12.0 and a["jours_detenue"] == 10
    assert r["risque_total"]["perte_si_tous_les_stops_usd"] == 160 and r["risque_total"]["pct_du_compte"] == 0.16
    assert r["poids_par_secteur_pct"] == {"Santé": 2.0}


def test_montant_selon_le_risque():
    from bot.risk import montant_selon_risque
    assert montant_selon_risque(100_000, 5, "moyen") == 12_000  # 0,6 % du compte / 5 % de stop
    assert montant_selon_risque(100_000, 8, "eleve") == 11_250
    assert montant_selon_risque(100_000, 10, "faible") == 4_000
    assert montant_selon_risque(100_000, 5, None) == 12_000 and montant_selon_risque(100_000, None) is None


def test_test_des_criteres_sur_le_passe():
    import datetime as dt
    from bot import backtest

    start = dt.date(2023, 1, 2)
    dates = [(start + dt.timedelta(days=i)).isoformat() for i in range(420)]
    def bars(f):
        return [{"t": d, "o": f(i), "h": f(i) * 1.01, "l": f(i) * 0.99, "c": f(i), "v": 1000} for i, d in enumerate(dates)]
    universe = {f"U{k}": bars(lambda i, k=k: 100 * (1 + 0.001 * k) ** i) for k in range(60)}  # 60 titres en hausse régulière
    r = backtest.run(universe, bars(lambda i: 100 * 1.0005 ** i))
    t = r["criteres"]["tendance_haussiere"]["20j"]
    assert r["valeurs"] == 60 and t["signaux"] > 0 and t["gagnants_pct"] == 100 and t["ecart_points"] > 0
    assert "tendance_haussiere" in backtest.summary(r)


def test_portefeuille_fantome():
    def bars(rows):
        return [{"t": d, "o": o, "h": h, "l": lo, "c": c} for d, o, h, lo, c in rows]
    aaa = bars([("2026-10-01", 100, 101, 99, 100), ("2026-10-02", 100, 113, 99, 112), ("2026-10-05", 112, 113, 110, 111)])
    bbb = bars([("2026-10-01", 50, 51, 49, 50), ("2026-10-02", 50, 50, 44, 45), ("2026-10-05", 45, 46, 44, 45)])
    spy = bars([("2026-10-01", 1, 1, 1, 100), ("2026-10-02", 1, 1, 1, 101), ("2026-10-05", 1, 1, 1, 102)])
    props = [{"auteur": "qualite", "action": "acheter", "symbole": "AAA", "prix_ref": 100, "montant": 10_000, "date": "2026-10-01",
              "stop_loss_pct": 5, "take_profit_pct": 10},
             {"auteur": "qualite", "action": "acheter", "symbole": "BBB", "prix_ref": 50, "montant": 10_000, "date": "2026-10-01",
              "stop_loss_pct": 8, "take_profit_pct": 16}]
    r = classement.shadow_portfolios(props, {"AAA": aaa, "BBB": bbb}, spy, ["qualite", "sentiment"])
    q = r["analystes"]["qualite"]
    assert q["ventes"] == 2 and q["gagnantes"] == 1  # AAA à l'objectif (+10 %), BBB au stop (-8 %)
    assert q["valeur"] == 100_200.0 and r["sp500_pct"] == 2.0 and "sentiment" not in r["analystes"]


def test_bilan_d_un_analyste():
    props = [{"auteur": "qualite", "symbole": "AAA", "prix_ref": 100, "date": "2026-10-01", "retenue": True, "verdict": "ok"},
             {"auteur": "qualite", "symbole": "BBB", "prix_ref": 50, "date": "2026-10-02", "retenue": False, "verdict": "rejet"}]
    data = classement.compute(props, {"AAA": 110, "BBB": 45}, ["qualite", "sentiment"])
    q = data["analystes"][0]
    assert q["id"] == "qualite" and q["rendement_moyen"] == 0.0 and q["reussite_pct"] == 50
    assert data["critique"] == {"avis": 2, "justes_pct": 100}  # ok sur +10 %, rejet sur -10 %
    txt = classement.summary("analyste", "qualite", data, {})
    assert "2 idée(s)" in txt and "+10,0 %" in txt and "trop petit" in txt
    assert classement.summary("analyste", "sentiment", data, {}) == ""  # pas encore d'idée


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("OK", name)
