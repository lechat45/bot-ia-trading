"""Tests des garde-fous et des sous-comptes. Lancer : python tests/test_risk.py"""
import datetime as dt
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot import comptes as comptes_mod  # noqa: E402
from bot import memory  # noqa: E402
from bot.comptes import Comptes  # noqa: E402
from bot.config import Config  # noqa: E402
from bot.executor import Broker  # noqa: E402
from bot.fakes import PRICES, FakeAlpaca  # noqa: E402
from bot.risk import check_buy, check_sell, check_stop  # noqa: E402

TMP = Path(tempfile.mkdtemp())
memory.ROOT = TMP  # les tests n'écrivent jamais dans la vraie mémoire
comptes_mod.PATH = TMP / "comptes.json"


def cfg():
    return Config(gemini_keys=[], groq_keys=[], alpaca_key="", alpaca_secret="", paper=True,
                  live_refused=False, dry_run=False)


def val(cash=100_000, positions=()):
    invested = sum(p["valeur"] for p in positions)
    return {"cash": cash, "valeur": cash + invested, "positions": list(positions)}


XOM = {"symbole": "XOM", "qty": 20, "valeur": 2200, "stop": 100.0, "en_attente": False}


def test_achat_valide():
    ok, msg, d = check_buy(cfg(), "a", val(), "AAPL", 200, 4000, 7, 15, [])
    assert ok and d["qty"] == 20 and d["stop"] == 186 and d["tp"] == 230


def test_limite_par_titre_et_clamp():
    ok, msg, _ = check_buy(cfg(), "a", val(), "AAPL", 200, 20000, 7, 15, [])
    assert not ok and "maximum 15000" in msg  # 15 % du compte de l'équipe
    ok, _, d = check_buy(cfg(), "a", val(), "AAPL", 200, 20000, 7, 15, [], clamp=True)
    assert ok and d["qty"] == 75


def test_stop_et_ratio():
    assert "entre 1 et 15" in check_buy(cfg(), "a", val(), "AAPL", 200, 4000, 30, 60, [])[1]
    assert "ratio" in check_buy(cfg(), "a", val(), "AAPL", 200, 4000, 8, 10, [])[1]
    assert "obligatoires" in check_buy(cfg(), "a", val(), "AAPL", 200, 4000, None, None, [])[1]


def test_penny_et_cash_reserve():
    assert "penny" in check_buy(cfg(), "a", val(), "PENY", 2, 1000, 5, 10, [])[1]
    ok, msg, _ = check_buy(cfg(), "a", val(cash=20000), "AAPL", 200, 4000, 7, 15, [], reserved=18000)
    assert not ok and "liquidités" in msg


def test_anti_aller_retour():
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    j = [{"type": "execution", "agent": "a", "ts": now, "action": "vendre", "symbole": "AAPL", "statut": "exécuté"}]
    assert "aller-retour" in check_buy(cfg(), "a", val(), "AAPL", 200, 4000, 7, 15, j)[1]
    assert check_buy(cfg(), "b", val(), "AAPL", 200, 4000, 7, 15, j)[0]  # une autre IA n'est pas concernée
    j = [{"type": "execution", "agent": "a", "ts": now, "action": "acheter", "symbole": "XOM", "statut": "exécuté"}]
    assert "journée" in check_sell(cfg(), "a", val(positions=[XOM]), "XOM", 100, j)[1]


def test_vente_et_stop():
    ok, _, d = check_sell(cfg(), "a", val(positions=[XOM]), "XOM", 50, [])
    assert ok and d["qty"] == 10
    assert "ne détenez pas" in check_sell(cfg(), "a", val(), "XOM", 100, [])[1]
    assert "jamais" in check_stop(cfg(), val(positions=[XOM]), "XOM", 95, 110)[1]
    assert check_stop(cfg(), val(positions=[XOM]), "XOM", 104, 110)[0]


def test_frein_d_urgence():
    ok, msg, _ = check_buy(cfg(), "a", val(), "AAPL", 200, 4000, 7, 15, [], frein="perte de 3,5 % aujourd'hui")
    assert not ok and "frein" in msg
    assert check_sell(cfg(), "a", val(positions=[XOM]), "XOM", 100, [])[0]  # les ventes restent possibles


def test_limite_par_secteur():
    # 35 % du compte (35 000 $) par secteur : 30 000 $ déjà dans la tech, il reste 5 000 $
    ok, msg, _ = check_buy(cfg(), "a", val(), "AAPL", 200, 8000, 7, 15, [], secteur="Technology", secteur_valeur=30000)
    assert not ok and "secteur" in msg and "maximum 5000" in msg
    ok, _, d = check_buy(cfg(), "a", val(), "AAPL", 200, 8000, 7, 15, [], clamp=True, secteur="Technology",
                         secteur_valeur=30000)
    assert ok and d["qty"] == 25
    assert check_buy(cfg(), "a", val(), "AAPL", 200, 8000, 7, 15, [], secteur=None, secteur_valeur=30000)[0]


def test_pas_d_achat_avant_les_resultats():
    assert "résultats" in check_buy(cfg(), "a", val(), "AAPL", 200, 4000, 7, 15, [], jours_resultats=1)[1]
    assert "résultats" in check_buy(cfg(), "a", val(), "AAPL", 200, 4000, 7, 15, [], jours_resultats=0)[1]
    assert check_buy(cfg(), "a", val(), "AAPL", 200, 4000, 7, 15, [], jours_resultats=5)[0]
    assert check_buy(cfg(), "a", val(), "AAPL", 200, 4000, 7, 15, [], jours_resultats="inconnue")[0]


def test_controle_du_registre():
    c = Comptes.load(["equipe"], 100_000, persist=False)
    c.add_lot("equipe", "AAPL", {"qty": 10, "prix": 200, "statut": "ouvert"}, "")
    c.add_lot("equipe", "MSFT", {"qty": 5, "prix": 400, "statut": "en_attente"}, "")
    assert c.reconcile({"AAPL": 10}) == []  # l'achat en attente n'est pas compté
    ecarts = c.reconcile({"AAPL": 7, "TSLA": 3})
    assert ecarts == ["AAPL : 10 au registre, 7 chez Alpaca", "TSLA : 0 au registre, 3 chez Alpaca"]


def test_sous_comptes_parcours_complet():
    alpaca = FakeAlpaca(open_=True)
    c = Comptes.load(["a", "b"], 50_000, persist=False)
    assert c.agent("a")["cash"] == 25_000
    b = Broker(alpaca, c, dry_run=False)
    r = b.buy("a", "AAPL", 20, 7, 15, "thèse")
    assert r["ok"] and c.agent("a")["cash"] == 21_000
    lot = c.agent("a")["positions"]["AAPL"]["lots"][0]
    assert lot["stop_id"] and lot["tp_id"] and lot["stop"] == 186
    # stop remonté : l'ordre Alpaca est remplacé et le registre suit le nouvel identifiant
    old = lot["stop_id"]
    assert b.adjust_stop("a", "AAPL", 190)["ok"] and lot["stop_id"] != old and lot["stop"] == 190
    # vente partielle : la protection est remise sur ce qui reste
    r = b.sell("a", "AAPL", 5)
    assert r["ok"] and c.agent("a")["cash"] == 22_000
    pos = c.agent("a")["positions"]["AAPL"]
    assert c.position_qty(pos) == 15 and pos["lots"][0]["stop"] == 190 and pos["lots"][0]["stop_id"]
    # le stop se déclenche chez Alpaca entre deux séances : la synchro le détecte
    alpaca.orders[pos["lots"][0]["stop_id"]].update(status="filled", filled_avg_price="189")
    c.sync(alpaca)
    assert "AAPL" not in c.agent("a")["positions"]
    assert c.agent("a")["cash"] == 22_000 + 15 * 189
    assert any("Stop loss déclenché" in e["texte"] for e in c.agent("a")["evenements"])
    assert c.agent("b")["cash"] == 25_000  # l'autre IA n'est pas touchée


def test_live_refuse_sans_confirmation():
    import os
    os.environ["ALPACA_PAPER"] = "false"
    os.environ.pop("LIVE_TRADING_CONFIRMATION", None)
    try:
        c = Config.from_env()
        assert c.paper and c.live_refused
    finally:
        os.environ["ALPACA_PAPER"] = "true"


if __name__ == "__main__":
    PRICES.setdefault("AAPL", 200.0)
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("OK", name)
