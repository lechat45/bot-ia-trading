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
    assert used.startswith("gemini#1") and msg["text"] == "ok"
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


def test_quota_du_jour_gemini():
    jour = SimpleNamespace(text='{"error":{"details":[{"quotaId":"GenerateRequestsPerDayPerProjectPerModel-FreeTier"},'
                                '{"retryDelay":"30s"}]}}', headers={})
    minute = SimpleNamespace(text='{"error":{"details":[{"quotaId":"GenerateRequestsPerMinutePerProjectPerModel"},'
                                  '{"retryDelay":"17s"}]}}', headers={})
    assert llm._gemini_wait(jour) == 3600 and llm._gemini_wait(minute) == 17


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
