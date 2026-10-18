"""Clients Gemini et Groq + routeur qui fait travailler les 6 clés ensemble.

Chaque agent a sa clé attitrée. Si elle est limitée (429) ou en erreur, le routeur
bascule sur les autres clés du même fournisseur, puis sur l'autre fournisseur.
"""
import json
import logging
import random
import re
import time
from collections import defaultdict

import requests

log = logging.getLogger("llm")


class LLMError(Exception):
    pass


class RateLimited(Exception):
    def __init__(self, wait: float):
        super().__init__(f"limite atteinte, attendre {wait:.0f}s")
        self.wait = wait


def extract_json(text: str) -> dict:
    t = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", t, re.S)
    if m:
        t = m.group(1)
    start, end = t.find("{"), t.rfind("}")
    if start < 0 or end < start:
        raise LLMError(f"pas de JSON dans la réponse : {text[:200]!r}")
    return json.loads(t[start : end + 1])


def _retry_after(resp: requests.Response, default: float) -> float:
    try:
        return float(resp.headers.get("retry-after", default))
    except ValueError:
        return default


def choose_model(available: list[str], prefs: list[str], must=(), avoid=()) -> str:
    for p in prefs:
        if p in available:
            return p
    candidates = sorted(
        (n for n in available if all(m in n for m in must) and not any(a in n for a in avoid)),
        reverse=True,
    )
    if not candidates:
        raise LLMError(f"aucun modèle utilisable parmi {available[:20]}")
    return candidates[0]


class Gemini:
    name = "gemini"
    URL = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(self, keys: list[str], prefs: list[str]):
        self.keys, self.prefs = keys, prefs
        self.models: list[str] = []  # modèles utilisables, du préféré au moins préféré
        self.idx = 0

    @property
    def model(self):
        return self.models[self.idx] if self.models else None

    def _load_models(self, key: str) -> None:
        if self.models:
            return
        r = requests.get(f"{self.URL}/models", params={"pageSize": 1000},
                         headers={"x-goog-api-key": key}, timeout=30)
        if r.status_code >= 400:
            raise LLMError(f"Gemini liste des modèles {r.status_code}: {r.text[:200]}")
        names = [m["name"].removeprefix("models/") for m in r.json().get("models", [])
                 if "generateContent" in m.get("supportedGenerationMethods", [])]
        avoid = ("image", "tts", "audio", "live", "embedding", "exp")
        ordered = [p for p in self.prefs if p in names]
        ordered += sorted((n for n in names if "gemini" in n and "flash" in n and n not in ordered
                           and not any(a in n for a in avoid)), reverse=True)
        if not ordered:
            raise LLMError(f"aucun modèle Gemini utilisable parmi {names[:20]}")
        self.models = ordered[:4]
        log.info("Gemini : modèle choisi %s (secours : %s)", self.models[0], ", ".join(self.models[1:]))

    def call(self, key, system, user, json_mode, search, max_tokens):
        self._load_models(key)
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0.6, "maxOutputTokens": max_tokens},
        }
        if search:
            body["tools"] = [{"google_search": {}}]
        elif json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"
        while True:
            model = self.model
            r = requests.post(f"{self.URL}/models/{model}:generateContent",
                              headers={"x-goog-api-key": key}, json=body, timeout=300)
            # Modèle surchargé (503) ou retiré (404) : on passe au modèle Gemini suivant.
            if r.status_code in (503, 404) and self.idx < len(self.models) - 1:
                self.idx += 1
                log.warning("Gemini : %s indisponible (%s), bascule sur %s", model, r.status_code, self.model)
                continue
            break
        if r.status_code == 429:
            raise RateLimited(_retry_after(r, 30))
        if r.status_code >= 400:
            raise LLMError(f"Gemini {r.status_code}: {r.text[:300]}")
        data = r.json()
        cands = data.get("candidates") or []
        if not cands:
            raise LLMError(f"Gemini : réponse vide {str(data)[:200]}")
        parts = cands[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        u = data.get("usageMetadata", {})
        return text, u.get("totalTokenCount", 0), model


class Groq:
    name = "groq"
    URL = "https://api.groq.com/openai/v1"

    def __init__(self, keys: list[str], prefs: list[str]):
        self.keys, self.prefs, self.model = keys, prefs, None

    def _pick_model(self, key: str) -> str:
        if not self.model:
            r = requests.get(f"{self.URL}/models", headers={"Authorization": f"Bearer {key}"},
                             timeout=30)
            if r.status_code >= 400:
                raise LLMError(f"Groq liste des modèles {r.status_code}: {r.text[:200]}")
            ids = [m["id"] for m in r.json().get("data", [])]
            self.model = choose_model(ids, self.prefs, avoid=(
                "whisper", "tts", "guard", "playai", "orpheus", "compound", "distil"))
            log.info("Groq : modèle choisi %s", self.model)
        return self.model

    def call(self, key, system, user, json_mode, search, max_tokens):
        model = self._pick_model(key)
        body = {
            "model": model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "temperature": 0.6,
            "max_completion_tokens": max_tokens,
        }
        if "gpt-oss" in model:
            body["reasoning_effort"] = "medium"
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        r = requests.post(f"{self.URL}/chat/completions",
                          headers={"Authorization": f"Bearer {key}"}, json=body, timeout=180)
        if r.status_code == 400 and json_mode and "json" in r.text.lower():
            # Le mode JSON strict a échoué : on retente sans et on extrait le JSON nous-mêmes.
            body.pop("response_format")
            r = requests.post(f"{self.URL}/chat/completions",
                              headers={"Authorization": f"Bearer {key}"}, json=body, timeout=180)
        if r.status_code == 429:
            raise RateLimited(_retry_after(r, 20))
        if r.status_code >= 400:
            raise LLMError(f"Groq {r.status_code}: {r.text[:300]}")
        data = r.json()
        text = data["choices"][0]["message"].get("content") or ""
        return text, data.get("usage", {}).get("total_tokens", 0), model


class Router:
    def __init__(self, cfg):
        self.providers = {
            "gemini": Gemini(cfg.gemini_keys, cfg.gemini_models),
            "groq": Groq(cfg.groq_keys, cfg.groq_models),
        }
        self.tokens = defaultdict(int)  # "gemini#1" -> tokens consommés
        self.calls = defaultdict(int)

    def _order(self, provider: str, key_index: int) -> list[tuple[str, int]]:
        order = []
        n = len(self.providers[provider].keys)
        order += [(provider, (key_index + j) % n) for j in range(n)]
        other = "groq" if provider == "gemini" else "gemini"
        order += [(other, j) for j in range(len(self.providers[other].keys))]
        return order

    def ask(self, provider, key_index, system, user, *, search=False, json_mode=True,
            max_tokens=8192, label=""):
        """Renvoie (réponse JSON ou texte, "fournisseur#clé:modèle")."""
        last = None
        order = self._order(provider, key_index)
        for prov_name, ki in order:
            prov = self.providers[prov_name]
            use_search = search and prov_name == "gemini"
            for attempt in range(2):
                try:
                    text, tokens, model = prov.call(prov.keys[ki], system, user, json_mode,
                                                    use_search, max_tokens)
                    slot = f"{prov_name}#{ki + 1}"
                    self.tokens[slot] += tokens
                    self.calls[slot] += 1
                    out = extract_json(text) if json_mode else text
                    if (prov_name, ki) != order[0]:
                        log.info("%s : relais assuré par %s", label, slot)
                    return out, f"{slot}:{model}"
                except RateLimited as e:
                    last = e
                    log.warning("%s : %s#%d limité (%s)", label, prov_name, ki + 1, e)
                    if attempt == 0 and e.wait <= 65:
                        time.sleep(e.wait + random.uniform(1, 4))
                        continue
                    break
                except (LLMError, requests.RequestException, ValueError, KeyError) as e:
                    last = e
                    log.warning("%s : échec %s#%d : %s", label, prov_name, ki + 1, e)
                    if use_search:
                        use_search = False  # on retente sans recherche Google
                        continue
                    if isinstance(e, ValueError) and attempt == 0:
                        continue  # JSON mal formé : une seconde chance
                    break
        raise LLMError(f"{label} : tous les fournisseurs ont échoué ({last})")
