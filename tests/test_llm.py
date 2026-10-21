"""Tests du relais entre clés et modèles (sans réseau). Lancer : python tests/test_llm.py"""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot import llm  # noqa: E402
from bot.llm import ModelUnavailable, RateLimited, Router  # noqa: E402


class FakeProvider:
    """Répond selon un scénario {(clé, modèle): exception à lever} ; compte les appels."""

    def __init__(self, keys, models, fail):
        self.keys, self.models, self.fail, self.calls = keys, set(models), fail, []

    def available(self, key):
        return self.models

    def chat(self, key, model, system, messages, tools):
        self.calls.append((key, model))
        err = self.fail.get((key, model))
        if err:
            raise err
        return {"role": "assistant", "text": "ok"}, 10


def router(gemini_fail, groq_fail):
    r = Router(SimpleNamespace(gemini_keys=["g1", "g2", "g3"], groq_keys=["q1", "q2", "q3"]))
    gm, qm = llm.DEFAULT_MODELS["gemini"], llm.DEFAULT_MODELS["groq"]
    r.providers = {"gemini": FakeProvider(["g1", "g2", "g3"], gm, gemini_fail),
                   "groq": FakeProvider(["q1", "q2", "q3"], qm, groq_fail)}
    return r


def test_un_modele_sature_n_est_plus_reessaye():
    qm = llm.DEFAULT_MODELS["groq"]
    groq_fail = {(k, m): RateLimited(1800, "Rate limit reached") for k in ("q1", "q2", "q3") for m in qm}
    r = router({}, groq_fail)
    agent = SimpleNamespace(id="critique", provider="groq", key_index=2, models=qm)
    msg, used = r.chat(agent, "", [], [])
    assert used.startswith("gemini#3") and msg["text"] == "ok"  # relais : la clé Gemini du même numéro d'abord
    first = len(r.providers["groq"].calls)
    assert first == 9  # 3 clés x 3 modèles essayés une fois
    r.chat(agent, "", [], [])  # 2e tour : les modèles Groq saturés sont sautés
    assert len(r.providers["groq"].calls) == first


def test_surcharge_passagere_mise_de_cote():
    gm = llm.DEFAULT_MODELS["gemini"]
    r = router({("g1", gm[0]): ModelUnavailable("503")}, {})
    agent = SimpleNamespace(id="qualite", provider="gemini", key_index=0, models=gm)
    assert r.chat(agent, "", [], [])[1] == f"gemini#1:{gm[1]}"
    r.chat(agent, "", [], [])
    assert r.providers["gemini"].calls.count(("g1", gm[0])) == 1


def test_requete_trop_grosse_passe_au_modele_suivant():
    qm = llm.DEFAULT_MODELS["groq"]
    r = router({}, {("q2", "qwen/qwen3.8-27b"): llm.ContextTooLarge("Request too large ... Limit 7000")})
    agent = SimpleNamespace(id="contrarien", provider="groq", key_index=1, models=["qwen/qwen3.8-27b"] + qm[:1])
    msgs = [{"role": "user", "text": "x" * 5000}]
    msg, used = r.chat(agent, "", msgs, [])
    assert msg["text"] == "ok" and used == f"groq#2:{qm[0]}"  # l'IA continue au lieu de s'arrêter
    r.chat(agent, "", msgs, [])  # même taille : Qwen n'est pas réessayé
    assert r.providers["groq"].calls.count(("q2", "qwen/qwen3.8-27b")) == 1


def test_quota_du_jour_gemini():
    jour = SimpleNamespace(text='{"error":{"details":[{"quotaId":"GenerateRequestsPerDayPerProjectPerModel-FreeTier"},'
                                '{"retryDelay":"30s"}]}}', headers={})
    minute = SimpleNamespace(text='{"error":{"details":[{"quotaId":"GenerateRequestsPerMinutePerProjectPerModel"},'
                                  '{"retryDelay":"17s"}]}}', headers={})
    assert 600 <= llm._gemini_wait(jour) <= 25 * 3600  # jusqu'à minuit en Californie
    assert llm._gemini_wait(minute) == 17


def test_saturations_gardees_entre_les_seances():
    qm = llm.DEFAULT_MODELS["groq"]
    r = router({}, {(k, m): RateLimited(1800, "TPD") for k in ("q1", "q2", "q3") for m in qm})
    agent = SimpleNamespace(id="sentiment", provider="groq", key_index=0, models=qm)
    r.chat(agent, "", [], [])
    saved = r.export_quotas()
    assert len(saved) == 9 and all(k.startswith("groq|") for k in saved)
    r2 = router({}, {})  # séance suivante : les modèles saturés sont sautés d'emblée
    assert r2.load_quotas({"satures": saved}) == 9
    assert r2.saturated_share([agent]) == 1.0
    r2.chat(agent, "", [], [])
    assert r2.providers["groq"].calls == []


def test_relais_vers_mistral():
    r = router({}, {})
    r.providers["mistral"] = FakeProvider(["m1"], llm.DEFAULT_MODELS["mistral"], {})
    attempts = r._attempts("groq", 1, ["qwen/qwen3.8-27b"])
    assert attempts[3][0] == "mistral"  # Groq saturé : Mistral avant Gemini
    assert r._attempts("mistral", 0, llm.DEFAULT_MODELS["mistral"])[3][0] == "gemini"


def test_roue_de_secours_gemma():
    from bot.agents import AGENTS

    qualite = next(a for a in AGENTS if a.id == "qualite")
    assert qualite.models[0].startswith("gemini") and qualite.models[-len(llm.GEMMA_MODELS):] == llm.GEMMA_MODELS
    r = router({}, {})
    relais = [m for p, _, m in r._attempts("groq", 0, ["openai/gpt-oss-120b"]) if p == "gemini"]
    assert relais[:len(llm.GEMMA_MODELS)] == llm.GEMMA_MODELS  # Groq saturé : Gemma avant le peu de quota Gemini
    gemma = {"role": "assistant", "raw_gemini": [{"functionCall": {"name": "screener", "args": {}, "id": "a"}}]}
    part = llm.Gemini.render([gemma])[0]["parts"][0]
    assert part["thoughtSignature"]  # Gemini peut reprendre une conversation où Gemma a appelé un outil


def test_limite_groq_commune_a_toutes_les_cles():
    qm = llm.DEFAULT_MODELS["groq"]
    r = router({}, {(k, qm[0]): RateLimited(40, "TPM", shared=True) for k in ("q1", "q2", "q3")})
    agent = SimpleNamespace(id="sentiment", provider="groq", key_index=0, models=qm[:1])
    t = __import__("time").time()
    msg, used = r.chat(agent, "", [], [])
    assert __import__("time").time() - t < 5  # pas de pause de 40 s : on passe tout de suite au relais
    assert used.startswith("gemini#1") and r.providers["groq"].calls == [("q1", qm[0])]  # les clés 2 et 3 sautées
    assert r._cool_left("groq", 2, qm[0]) > 30


def test_trop_gros_pour_groq_mais_relais_juste_limite():
    qm = llm.DEFAULT_MODELS["groq"]
    gm = llm.DEFAULT_MODELS["gemini"]
    big = {(k, m): llm.ContextTooLarge("Request too large") for k in ("q1", "q2", "q3") for m in qm}
    r = router({(k, m): RateLimited(300, "par minute") for k in ("g1", "g2", "g3") for m in gm}, big)
    agent = SimpleNamespace(id="critique", provider="groq", key_index=2, models=qm)
    try:
        r._chat_once(agent, "", [{"role": "user", "text": "x"}], [], "critique", r._attempts("groq", 2, qm))
        raise AssertionError("aucun modèle ne devait répondre")
    except llm.ContextTooLarge:
        raise AssertionError("le relais est seulement limité : il faut attendre, pas raccourcir la conversation")
    except llm.LLMError:
        pass


def test_recherche_web_de_secours():
    from bot import tools

    gm = llm.DEFAULT_MODELS["gemini"]

    class GeminiEpuise(FakeProvider):
        def search(self, key, model, question):
            self.calls.append((key, model))
            raise RateLimited(3600, "PerDay")

    r = router({}, {})
    r.providers["gemini"] = GeminiEpuise(["g1", "g2", "g3"], gm, {})
    old_free, old_tav = tools.free_search, tools.tavily_configured
    tools.tavily_configured = lambda: False
    tools.free_search = lambda q: {"actualites_google": [{"titre": f"Article sur {q}", "source": "Reuters"}]}
    try:
        res = r.web_search("Nvidia earnings date", who="qualite")
        assert res["moteur"].startswith("Google Actualités") and res["actualites_google"][0]["source"] == "Reuters"
        n = len(r.providers["gemini"].calls)
        assert n == 9  # 3 clés x 3 modèles, une seule fois, sans pause
        res = r.web_search("Nvidia stock news today", who="sentiment")
        assert len(r.providers["gemini"].calls) == n  # Gemini épuisé n'est plus réessayé
        assert r.web_search("nvidia EARNINGS date ?", who="gerant").get("cache")  # même question = mémoire
    finally:
        tools.free_search, tools.tavily_configured = old_free, old_tav


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("OK", name)
