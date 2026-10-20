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
