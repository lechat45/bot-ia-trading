"""Vérifie chaque clé du fichier .env sans jamais l'afficher.

    python check_keys.py
"""
import requests

from bot.config import Config


def mask(key: str) -> str:
    return f"…{key[-4:]}" if len(key) > 8 else "…"


def check_gemini(key):
    r = requests.get("https://generativelanguage.googleapis.com/v1beta/models", params={"pageSize": 1000},
                     headers={"x-goog-api-key": key}, timeout=20)
    if r.status_code != 200:
        return False, f"HTTP {r.status_code}"
    names = [m["name"].removeprefix("models/") for m in r.json().get("models", [])
             if "generateContent" in m.get("supportedGenerationMethods", [])]
    return True, f"{len(names)} modèles"


def check_groq(key):
    r = requests.get("https://api.groq.com/openai/v1/models", headers={"Authorization": f"Bearer {key}"},
                     timeout=20)
    if r.status_code != 200:
        return False, f"HTTP {r.status_code}"
    return True, f"{len(r.json().get('data', []))} modèles"


def main():
    cfg = Config.from_env()
    ok_all = True
    print("Gemini :", f"{len(cfg.gemini_keys)}/3 clé(s)")
    for i, k in enumerate(cfg.gemini_keys, 1):
        ok, info = check_gemini(k)
        ok_all &= ok
        print(f"  {'OK ' if ok else 'ERR'} GEMINI_API_KEY_{i} {mask(k)} : {info}")
    print("Groq :", f"{len(cfg.groq_keys)}/3 clé(s)")
    for i, k in enumerate(cfg.groq_keys, 1):
        ok, info = check_groq(k)
        ok_all &= ok
        print(f"  {'OK ' if ok else 'ERR'} GROQ_API_KEY_{i} {mask(k)} : {info}")
    print("Alpaca :", "PAPER" if cfg.paper else "RÉEL")
    if cfg.alpaca_key and cfg.alpaca_secret:
        base = "https://paper-api.alpaca.markets" if cfg.paper else "https://api.alpaca.markets"
        r = requests.get(f"{base}/v2/account", timeout=20, headers={
            "APCA-API-KEY-ID": cfg.alpaca_key, "APCA-API-SECRET-KEY": cfg.alpaca_secret})
        if r.status_code == 200:
            a = r.json()
            print(f"  OK  compte {a.get('status')} · valeur {float(a['equity']):,.2f} $ · cash {float(a['cash']):,.2f} $")
        else:
            ok_all = False
            print(f"  ERR HTTP {r.status_code} (clé paper sur compte réel ou inversement ? clé régénérée ?)")
    else:
        ok_all = False
        print("  ERR ALPACA_API_KEY / ALPACA_SECRET_KEY manquantes")
    for p in cfg.problems():
        print("  !", p)
    print("\nTout est bon." if ok_all else "\nIl reste des clés à corriger.")


if __name__ == "__main__":
    main()
