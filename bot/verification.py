"""Vérification complète de l'installation : tout est testé avant de laisser les IA trader.

Lancée automatiquement au premier lancement (et tant qu'elle n'a pas réussi), ou à la demande :
    python main.py --verifier

Chaque test est « critique » (sans lui, pas de séance) ou « utile » (la séance peut tourner,
mais un outil des IA sera moins bon). Le résultat est enregistré dans memoire/installation.json
et affiché sur l'Accueil du tableau de bord.
"""
import datetime as dt
import logging
import subprocess
import sys
import time
from pathlib import Path

from . import memory, tools

log = logging.getLogger("verif")
ROOT = Path(__file__).resolve().parent.parent
TEST_TOOL = [{"name": "test_outil", "description": "Outil de test : donne le prix d'une action.",
              "parameters": {"type": "object", "properties": {"symbole": {"type": "string"}}, "required": ["symbole"]}}]


class Checks:
    def __init__(self):
        self.rows: list[dict] = []

    def run(self, cid, nom, niveau, fn):
        start = time.time()
        try:
            ok, detail = fn()
        except Exception as e:  # un test qui plante est un test en échec, pas un arrêt du programme
            ok, detail = False, f"{type(e).__name__} : {str(e)[:200]}"
        self.rows.append({"id": cid, "nom": nom, "niveau": niveau, "ok": ok is True,
                          "attention": ok is None, "detail": detail, "duree_s": round(time.time() - start, 1)})
        tag = "OK       " if ok is True else ("ATTENTION" if ok is None else "ÉCHEC    ")
        log.info("%s %-34s %s", tag, nom, detail)


def run(cfg, alpaca, router, offline: bool = False) -> dict:
    from .agents import AGENTS  # import tardif (évite une importation circulaire)
    from .risk import check_buy

    c = Checks()
    today = dt.datetime.now(dt.timezone.utc).date()

    # ------------------------------------------------------------- configuration et broker
    # hors ligne, le broker et les IA sont simulés : des clés absentes ne bloquent pas le test
    c.run("config", "Configuration (.env / Secrets)", "utile" if offline else "critique", lambda: (
        (not cfg.problems(), "clés présentes, mode " + ("paper (argent virtuel)" if cfg.paper else "ARGENT RÉEL"))
        if not cfg.problems() else (False, " ; ".join(cfg.problems()))))

    def compte():
        a = alpaca.account()
        if a.get("trading_blocked") or a.get("account_blocked"):
            return False, "compte Alpaca bloqué"
        return True, f"compte {a.get('status', 'ACTIVE')}, valeur {float(a['equity']):,.2f} $".replace(",", " ")
    c.run("alpaca_compte", "Compte Alpaca", "critique", compte)

    def horloge():
        k = alpaca.clock()
        return True, "bourse ouverte" if k.get("is_open") else f"bourse fermée, ouverture {k.get('next_open', '?')[:16]}"
    c.run("alpaca_horloge", "Horaires de la bourse", "critique", horloge)

    def cours():
        bars = alpaca.bars(["AAPL", "SPY"]).get("AAPL") or []
        px = alpaca.latest_prices(["AAPL"]).get("AAPL")
        if len(bars) < 200 or not px:
            return False, f"historique insuffisant ({len(bars)} jours) ou prix absent"
        return True, f"AAPL : {len(bars)} jours d'historique, dernier prix {px:.2f} $"
    c.run("cours", "Cours et historique des actions", "critique", cours)

    def actus():
        n = alpaca.news(limit=3)
        return (True, f"{len(n)} articles, ex. « {n[0].get('headline', '')[:60]} »") if n else (None, "aucun article reçu")
    c.run("actualites", "Fil d'actualité", "utile", actus)

    def screener():
        rows = alpaca.most_actives(5)
        return (True, f"{len(rows)} actions les plus échangées") if rows else (None, "screener vide")
    c.run("screener", "Screener du marché", "utile", screener)

    # ------------------------------------------------------------- sources gratuites
    if offline:
        for cid, nom in (("financier", "Données financières (yfinance)"), ("reddit", "Reddit (ApeWisdom)"),
                         ("web", "Recherche web (Google)"), ("page", "Lecture d'une page web")):
            c.rows.append({"id": cid, "nom": nom, "niveau": "utile", "ok": False, "attention": True,
                           "detail": "ignoré (test hors-ligne)", "duree_s": 0})
    else:
        def financier():
            f = tools.fundamentals("AAPL", today) or {}
            return (True, f"AAPL : PER {f.get('per')}, résultats {f.get('prochains_resultats')}") if f.get("nom") else (None, "pas de réponse de yfinance")
        c.run("financier", "Données financières (yfinance)", "utile", financier)

        def reddit():
            d = tools.reddit_trending()
            return (True, f"{len(d)} actions suivies, n°1 : {min(d.values(), key=lambda x: x.get('rank', 999))['ticker']}") if d else (None, "ApeWisdom ne répond pas")
        c.run("reddit", "Reddit (ApeWisdom)", "utile", reddit)
        if tools.reddit_oauth_configured():
            def reddit_msgs():
                posts = tools.reddit_posts("AAPL", limit=3)
                return (True, f"{len(posts)} messages lus") if posts else (None, "identifiants Reddit refusés ou aucun message")
            c.run("reddit_messages", "Reddit : lecture des messages", "utile", reddit_msgs)

        def web():
            r = router.web_search("En une phrase : quelle entreprise fabrique l'iPhone ?", who="verification")
            return (True, f"réponse : {r['reponse'][:60]}") if r.get("reponse") else (None, r.get("erreur", "pas de réponse"))
        c.run("web", "Recherche web (Google)", "utile", web)

        def page():
            r = tools.read_page("https://example.com")
            return (True, f"page lue : « {r.get('titre', '')} »") if r.get("texte") else (None, r.get("erreur", "page vide"))
        c.run("page", "Lecture d'une page web", "utile", page)

    # ------------------------------------------------------------- clés et modèles d'IA
    for prov in ("gemini", "groq"):
        p = router.providers[prov] if hasattr(router, "providers") else None
        keys = p.keys if p else []
        for i, key in enumerate(keys):
            c.run(f"cle_{prov}_{i + 1}", f"Clé {prov.capitalize()} n°{i + 1}", "utile",
                  lambda p=p, key=key: (True, f"{len(p.available(key))} modèles disponibles"))
    ok_keys = [r for r in c.rows if r["id"].startswith("cle_") and r["ok"]]
    if hasattr(router, "providers"):
        c.rows.append({"id": "cles", "nom": "Au moins une clé d'IA valide", "niveau": "critique", "ok": bool(ok_keys),
                       "attention": False, "detail": f"{len(ok_keys)} clé(s) valide(s)", "duree_s": 0})

    # ------------------------------------------------------------- chaque IA sait appeler un outil
    for a in AGENTS:
        def tool_call(a=a):
            msg, used = router.chat(a, "Tu es un test. Appelle l'outil demandé.",
                                    [{"role": "user", "text": "Appelle l'outil test_outil avec le symbole AAPL."}],
                                    TEST_TOOL, label=f"verif-{a.id}")
            if not msg.get("calls"):
                return False, f"le modèle a répondu sans appeler l'outil ({used})"
            own = used.startswith(f"{a.provider}#{a.key_index + 1}:")
            return (True if own else None), (f"appel d'outil réussi avec {used}" + ("" if own else " (clé de relais)"))
        c.run(f"ia_{a.id}", f"{a.nom} : appel d'outils", "utile", tool_call)
    ok_ia = [r for r in c.rows if r["id"].startswith("ia_") and (r["ok"] or r["attention"])]
    c.rows.append({"id": "ia", "nom": "Au moins une IA opérationnelle", "niveau": "critique", "ok": len(ok_ia) > 0,
                   "attention": False, "detail": f"{len(ok_ia)}/{len(AGENTS)} IA répondent avec des outils", "duree_s": 0})

    # ------------------------------------------------------------- garde-fous et mémoire
    def gardefous():
        val = {"cash": 100_000, "valeur": 100_000, "positions": []}
        bad, msg, _ = check_buy(cfg, "t", val, "AAPL", 200, 4000, 30, 60, [])  # stop de 30 % : doit être refusé
        good, _, d = check_buy(cfg, "t", val, "AAPL", 200, 4000, 7, 15, [])
        if bad or not good:
            return False, "les garde-fous ne réagissent pas comme prévu"
        r = subprocess.run([sys.executable, str(ROOT / "tests" / "test_risk.py")], capture_output=True, text=True,
                           cwd=ROOT, timeout=120, encoding="utf-8", errors="replace")
        n = r.stdout.count("OK test_")
        return (r.returncode == 0), (f"{n} tests réussis" if r.returncode == 0 else f"échec : {r.stdout[-200:]}{r.stderr[-200:]}")
    c.run("gardefous", "Garde-fous (stop, tailles, aller-retour)", "critique", gardefous)

    def memoire():
        p = memory.ROOT / ".test_ecriture"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("ok", encoding="utf-8")
        ok = p.read_text(encoding="utf-8") == "ok"
        p.unlink()
        return ok, "dossier memoire/ accessible en écriture"
    c.run("memoire", "Mémoire des IA", "critique", memoire)

    critical_fail = [r for r in c.rows if r["niveau"] == "critique" and not r["ok"]]
    res = {"date": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "ok": not critical_fail,
           "hors_ligne": offline, "reussis": sum(1 for r in c.rows if r["ok"]),
           "attention": sum(1 for r in c.rows if r["attention"]), "total": len(c.rows), "checks": c.rows}
    if not offline:
        memory.write_installation(res)
    log.info("Vérification : %d/%d réussis, %d avertissement(s), %s", res["reussis"], res["total"], res["attention"],
             "prêt à trader" if res["ok"] else "ÉCHEC CRITIQUE : " + ", ".join(r["nom"] for r in critical_fail))
    return res
