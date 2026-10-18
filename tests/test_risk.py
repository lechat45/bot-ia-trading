"""Tests des garde-fous. Lancer : python -m pytest tests  (ou python tests/test_risk.py)"""
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.config import Config  # noqa: E402
from bot.risk import Context, validate  # noqa: E402


def cfg():
    return Config(gemini_keys=[], groq_keys=[], alpaca_key="", alpaca_secret="", paper=True,
                  live_refused=False, dry_run=True)


def ctx(journal=None):
    return Context(
        equity=100_000, cash=50_000,
        positions={"XOM": {"qty": 100, "avg": 105, "price": 110, "value": 11_000}},
        prices={"XOM": 110, "AAPL": 200, "PENY": 2},
        exits={"XOM": {"stops": [("s1", 100.0)], "tps": [("t1", 125.0)]}},
        journal=journal or [],
    )


def buy(sym="AAPL", **kw):
    return {"action": "acheter", "symbole": sym, "poids_pct": 5, "stop_loss": 186, "take_profit": 230, **kw}


def test_achat_valide():
    ok, rej = validate([buy()], ctx(), cfg())
    assert not rej and ok[0]["qty"] == 25


def test_poids_plafonne():
    ok, _ = validate([buy(poids_pct=80)], ctx(), cfg())
    assert ok[0]["qty"] == 50  # 10 % max de 100 000 $ à 200 $


def test_stop_obligatoire():
    _, rej = validate([{"action": "acheter", "symbole": "AAPL", "poids_pct": 5}], ctx(), cfg())
    assert "obligatoires" in rej[0]["raison_rejet"]


def test_stop_trop_loin_et_ratio():
    _, rej = validate([buy(stop_loss=150), buy("XOM", stop_loss=108, take_profit=111)], ctx(), cfg())
    assert "trop loin" in rej[0]["raison_rejet"] and "ratio" in rej[1]["raison_rejet"]


def test_penny_stock():
    _, rej = validate([buy("PENY", stop_loss=1.8, take_profit=3)], ctx(), cfg())
    assert "penny" in rej[0]["raison_rejet"]


def test_stop_jamais_abaisse():
    ok, rej = validate([{"action": "ajuster_stop", "symbole": "XOM", "stop_loss": 95}], ctx(), cfg())
    assert not ok and "jamais" in rej[0]["raison_rejet"]
    ok, _ = validate([{"action": "ajuster_stop", "symbole": "XOM", "stop_loss": 104}], ctx(), cfg())
    assert ok


def test_anti_aller_retour():
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    j = [{"type": "execution", "ts": now, "action": "vendre", "symbole": "AAPL", "statut": "envoyé"}]
    _, rej = validate([buy()], ctx(j), cfg())
    assert "aller-retour" in rej[0]["raison_rejet"]


def test_pas_de_vente_sans_position_et_un_ordre_par_titre():
    ok, rej = validate([{"action": "vendre", "symbole": "AAPL"}, buy(), buy()], ctx(), cfg())
    assert len(ok) == 1 and len(rej) == 2


def test_cash_minimum():
    c = ctx()
    c.cash = 12_000  # plancher = 10 000 $ -> seulement 2 000 $ utilisables
    ok, _ = validate([buy()], c, cfg())
    assert ok[0]["qty"] == 10


def test_live_refuse_sans_confirmation(monkeypatch=None):
    import os
    os.environ["ALPACA_PAPER"] = "false"
    os.environ.pop("LIVE_TRADING_CONFIRMATION", None)
    try:
        c = Config.from_env()
        assert c.paper and c.live_refused
    finally:
        os.environ["ALPACA_PAPER"] = "true"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("OK", name)
