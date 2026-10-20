"""Construit bot/industries.json : le secteur et l'industrie de chaque valeur de l'univers (source :
Yahoo Finance). Il sert à trouver les concurrents d'une entreprise sans interroger Yahoo à chaque
séance. À relancer seulement si l'univers change :

    python outils/construire_industries.py
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import yfinance as yf  # noqa: E402

from bot.universe import UNIVERSE  # noqa: E402


def main():
    out = {}
    for i, sym in enumerate(UNIVERSE, 1):
        try:
            info = yf.Ticker(sym).info or {}
            out[sym] = {"secteur": info.get("sector"), "industrie": info.get("industry"),
                        "capitalisation": info.get("marketCap")}
        except Exception as e:  # une valeur manquante n'empêche pas les autres
            print(f"{sym} : {e}")
        if i % 20 == 0:
            print(f"{i}/{len(UNIVERSE)}")
        time.sleep(0.2)
    path = ROOT / "bot" / "industries.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    print(f"{len(out)} valeurs enregistrées dans {path}")


if __name__ == "__main__":
    main()
