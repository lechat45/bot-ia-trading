"""Clients Gemini et Groq avec APPEL D'OUTILS, et routeur qui fait travailler les 6 clés ensemble.

Comme chez Aywen, chaque IA décide seule quels outils utiliser : le modèle répond soit par du
texte, soit par des appels d'outils que le programme exécute avant de lui renvoyer le résultat.

La conversation est gardée dans un format neutre :
    {"role": "user", "text": ...}
    {"role": "assistant", "text": ..., "calls": [{"id", "name", "args"}], "raw_gemini": [...]}
    {"role": "tool", "id": ..., "name": ..., "content": "..."}
ce qui permet de passer d'une clé, d'un modèle ou même d'un fournisseur à l'autre en pleine séance
si l'un d'eux est saturé.
"""
import copy
import datetime as dt
import difflib
import hashlib
import json
import logging
import random
import re
import threading
import time
import uuid
from collections import defaultdict

import requests

log = logging.getLogger("llm")


class LLMError(Exception):
    pass


class RateLimited(LLMError):
    def __init__(self, wait: float, msg: str = ""):
        super().__init__(f"limite atteinte ({msg[:80]}), attendre {wait:.0f}s")
        self.wait = wait


class ModelUnavailable(LLMError):
    pass


class ContextTooLarge(LLMError):
    pass


def _retry_after(resp: requests.Response, default: float) -> float:
    try:
        return float(resp.headers.get("retry-after", default))
    except ValueError:
        return default


def _gemini_wait(resp: requests.Response) -> float:
    """Temps d'attente annoncé par Gemini. Un quota du JOUR épuisé (« PerDay ») ne revient pas avant des
    heures, même si la réponse propose de réessayer dans 30 secondes."""
    if "PerDay" in resp.text:  # remis à zéro à minuit, heure de Californie (9 h à Paris)
        from zoneinfo import ZoneInfo

        now = dt.datetime.now(ZoneInfo("America/Los_Angeles"))
        reset = (now + dt.timedelta(days=1)).replace(hour=0, minute=1, second=0, microsecond=0)
        return max(600.0, (reset - now).total_seconds())
    m = re.search(r'"retryDelay":\s*"(\d+(?:\.\d+)?)s"', resp.text)
    return float(m.group(1)) if m else _retry_after(resp, 30)


def _new_id() -> str:
    return "call_" + uuid.uuid4().hex[:10]


# ---------------------------------------------------------------------------- Gemini
class Gemini:
    name = "gemini"
    URL = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(self, keys: list[str]):
        self.keys = keys
        self._models: dict[str, set] = {}
        self._lock = threading.Lock()

    def available(self, key: str) -> set:
        with self._lock:
            if key not in self._models:
                r = requests.get(f"{self.URL}/models", params={"pageSize": 1000},
                                 headers={"x-goog-api-key": key}, timeout=30)
                if r.status_code >= 400:
                    raise LLMError(f"Gemini liste des modèles {r.status_code}: {r.text[:150]}")
                self._models[key] = {m["name"].removeprefix("models/") for m in r.json().get("models", [])
                                     if "generateContent" in m.get("supportedGenerationMethods", [])}
            return self._models[key]

    @staticmethod
    def render(messages: list[dict]) -> list[dict]:
        contents: list[dict] = []

        def add(role, parts):
            if contents and contents[-1]["role"] == role:
                contents[-1]["parts"].extend(parts)
            else:
                contents.append({"role": role, "parts": parts})

        for m in messages:
            if m["role"] == "user":
                add("user", [{"text": m["text"]}])
            elif m["role"] == "assistant":
                if m.get("raw_gemini"):
                    add("model", copy.deepcopy(m["raw_gemini"]))
                    continue
                parts = [{"text": m["text"]}] if m.get("text") else []
                for i, c in enumerate(m.get("calls", [])):
                    p = {"functionCall": {"name": c["name"], "args": c["args"], "id": c["id"]}}
                    if i == 0:  # conversation venue d'un autre modèle : signature factice autorisée
                        p["thoughtSignature"] = "skip_thought_signature_validator"
                    parts.append(p)
                add("model", parts or [{"text": "…"}])
            elif m["role"] == "tool":
                add("user", [{"functionResponse": {"name": m["name"], "id": m["id"],
                                                   "response": {"resultat": m["content"]}}}])
        return contents

    def _post(self, key, model, body, timeout=240):
        try:
            r = requests.post(f"{self.URL}/models/{model}:generateContent",
                              headers={"x-goog-api-key": key}, json=body, timeout=timeout)
        except requests.Timeout:
            raise ModelUnavailable(f"Gemini {model} : délai dépassé")
        if r.status_code == 429:
            raise RateLimited(_gemini_wait(r), r.text)
        if r.status_code in (404, 500, 503):
            raise ModelUnavailable(f"Gemini {model} {r.status_code}")
        if r.status_code == 400 and ("token" in r.text.lower() and "exceed" in r.text.lower()):
            raise ContextTooLarge(r.text[:200])
        if r.status_code >= 400:
            raise LLMError(f"Gemini {r.status_code}: {r.text[:300]}")
        return r.json()

    def chat(self, key, model, system, messages, tools, max_tokens=8192):
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": self.render(messages),
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": max_tokens},
        }
        if tools:
            body["tools"] = [{"functionDeclarations": tools}]
        data = self._post(key, model, body)
        cands = data.get("candidates") or []
        if not cands:
            raise LLMError(f"Gemini : réponse vide {str(data.get('promptFeedback', data))[:200]}")
        if cands[0].get("finishReason") == "MALFORMED_FUNCTION_CALL":
            raise LLMError("Gemini : appel d'outil mal formé")
        parts = (cands[0].get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        calls = [{"id": p["functionCall"].get("id") or _new_id(), "name": p["functionCall"]["name"],
                  "args": p["functionCall"].get("args") or {}} for p in parts if "functionCall" in p]
        msg = {"role": "assistant", "text": text.strip(), "calls": calls, "raw_gemini": parts}
        return msg, (data.get("usageMetadata") or {}).get("totalTokenCount", 0)

    def search(self, key, model, question):
        """Recherche Google (« Navigateur web » d'Aywen) grâce à l'ancrage Google Search de Gemini."""
        body = {
            "systemInstruction": {"parts": [{"text": (
                "Tu es un assistant de recherche pour un investisseur. Réponds en français, de façon "
                "factuelle et concise (10 lignes maximum), en donnant les dates et les chiffres précis. "
                "Si l'information est introuvable, dis-le clairement.")}]},
            "contents": [{"role": "user", "parts": [{"text": question}]}],
            "tools": [{"google_search": {}}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 4096},
        }
        data = self._post(key, model, body, timeout=120)
        cands = data.get("candidates") or []
        if not cands:
            raise LLMError("Gemini recherche : réponse vide")
        parts = (cands[0].get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
        chunks = (cands[0].get("groundingMetadata") or {}).get("groundingChunks") or []
        sources = [c["web"].get("title") for c in chunks if c.get("web")][:5]
        return text, sources, (data.get("usageMetadata") or {}).get("totalTokenCount", 0)


# ---------------------------------------------------------------------------- Groq
class Groq:
    name = "groq"
    URL = "https://api.groq.com/openai/v1"

    def __init__(self, keys: list[str]):
        self.keys = keys
        self._models: dict[str, set] = {}
        self._lock = threading.Lock()

    def available(self, key: str) -> set:
        with self._lock:
            if key not in self._models:
                r = requests.get(f"{self.URL}/models", headers={"Authorization": f"Bearer {key}"}, timeout=30)
                if r.status_code >= 400:
                    raise LLMError(f"Groq liste des modèles {r.status_code}: {r.text[:150]}")
                self._models[key] = {m["id"] for m in r.json().get("data", [])}
            return self._models[key]

    @staticmethod
    def render(system, messages):
        out = [{"role": "system", "content": system}]
        for m in messages:
            if m["role"] == "user":
                out.append({"role": "user", "content": m["text"]})
            elif m["role"] == "assistant":
                d = {"role": "assistant", "content": m.get("text") or ""}
                if m.get("calls"):
                    d["tool_calls"] = [{"id": c["id"], "type": "function", "function": {
                        "name": c["name"], "arguments": json.dumps(c["args"], ensure_ascii=False)}}
                        for c in m["calls"]]
                out.append(d)
            elif m["role"] == "tool":
                out.append({"role": "tool", "tool_call_id": m["id"], "content": m["content"]})
        return out

    @staticmethod
    def _repair_call(r, tools):
        """Le modèle a appelé un outil au nom mal orthographié (ex. « research_web ») : on retrouve
        l'outil le plus proche plutôt que de perdre le tour."""
        try:
            gen = json.loads(r.json()["error"].get("failed_generation") or "{}")
        except (ValueError, KeyError, TypeError):
            return None
        gen = gen[0] if isinstance(gen, list) and gen else gen
        if not isinstance(gen, dict) or not gen.get("name"):
            return None
        names = [t["name"] for t in tools]
        match = difflib.get_close_matches(gen["name"], names, n=1, cutoff=0.5)
        if not match:
            return None
        args = gen.get("arguments") or gen.get("parameters") or {}
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}
        log.info("Groq : appel « %s » corrigé en « %s »", gen["name"], match[0])
        return {"role": "assistant", "text": "", "calls": [{"id": _new_id(), "name": match[0],
                                                            "args": args if isinstance(args, dict) else {}}]}

    def chat(self, key, model, system, messages, tools, max_tokens=2000):
        body = {"model": model, "messages": self.render(system, messages), "temperature": 0.6,
                "max_completion_tokens": max_tokens}
        if tools:
            body["tools"] = [{"type": "function", "function": t} for t in tools]
            body["tool_choice"] = "auto"
        if "gpt-oss" in model:
            body["reasoning_effort"] = "medium"
        if "qwen" in model:
            body["reasoning_format"] = "hidden"
        try:
            r = requests.post(f"{self.URL}/chat/completions", headers={"Authorization": f"Bearer {key}"},
                              json=body, timeout=180)
        except requests.Timeout:
            raise ModelUnavailable(f"Groq {model} : délai dépassé")
        # « Request too large » arrive parfois en 429 : la requête dépasse ce que le modèle accepte en une
        # minute (ex. 7 000 tokens pour Qwen en gratuit). Attendre ne sert à rien, il faut un autre modèle.
        if r.status_code == 413 or "request too large" in r.text.lower() or (
                r.status_code == 400 and "context" in r.text.lower() and "length" in r.text.lower()):
            raise ContextTooLarge(r.text[:200])
        if r.status_code == 429:
            raise RateLimited(_retry_after(r, 20), r.text)
        if r.status_code in (404, 500, 502, 503):
            raise ModelUnavailable(f"Groq {model} {r.status_code}")
        if r.status_code == 400 and "tool_use_failed" in r.text and tools:
            fixed = self._repair_call(r, tools)
            if fixed:
                return fixed, 0
        if r.status_code >= 400:
            raise LLMError(f"Groq {r.status_code}: {r.text[:300]}")
        data = r.json()
        m = data["choices"][0]["message"]
        text = re.sub(r"<think>.*?</think>", "", m.get("content") or "", flags=re.S).strip()
        calls = []
        for c in m.get("tool_calls") or []:
            try:
                args = json.loads(c["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            calls.append({"id": c.get("id") or _new_id(), "name": c["function"]["name"],
                          "args": args if isinstance(args, dict) else {}})
        return {"role": "assistant", "text": text, "calls": calls}, data.get("usage", {}).get("total_tokens", 0)


# ---------------------------------------------------------------------------- Mistral
class Mistral(Groq):
    """Mistral (La Plateforme, formule gratuite « Experiment ») : même format que Groq, à deux détails près.
    Ses identifiants d'appel d'outil doivent faire 9 caractères (lettres et chiffres), et la longueur de
    réponse s'appelle max_tokens."""
    name = "mistral"
    URL = "https://api.mistral.ai/v1"

    @staticmethod
    def _id(raw: str) -> str:
        return hashlib.md5(str(raw).encode()).hexdigest()[:9]

    @classmethod
    def render(cls, system, messages):
        out = Groq.render(system, messages)
        for m in out:
            for c in m.get("tool_calls") or []:
                c["id"] = cls._id(c["id"])
            if m["role"] == "tool":
                m["tool_call_id"] = cls._id(m["tool_call_id"])
        return out

    def chat(self, key, model, system, messages, tools, max_tokens=2000):
        body = {"model": model, "messages": self.render(system, messages), "temperature": 0.6, "max_tokens": max_tokens}
        if tools:
            body["tools"] = [{"type": "function", "function": t} for t in tools]
            body["tool_choice"] = "auto"
        try:
            r = requests.post(f"{self.URL}/chat/completions", headers={"Authorization": f"Bearer {key}"},
                              json=body, timeout=180)
        except requests.Timeout:
            raise ModelUnavailable(f"Mistral {model} : délai dépassé")
        if r.status_code == 429:
            raise RateLimited(_retry_after(r, 15), r.text)
        if r.status_code in (404, 500, 502, 503):
            raise ModelUnavailable(f"Mistral {model} {r.status_code}")
        if r.status_code == 400 and "too large" in r.text.lower():
            raise ContextTooLarge(r.text[:200])
        if r.status_code >= 400:
            raise LLMError(f"Mistral {r.status_code}: {r.text[:300]}")
        data = r.json()
        m = data["choices"][0]["message"]
        calls = []
        for c in m.get("tool_calls") or []:
            args = c["function"].get("arguments") or "{}"
            try:
                args = json.loads(args) if isinstance(args, str) else args
            except json.JSONDecodeError:
                args = {}
            calls.append({"id": c.get("id") or _new_id(), "name": c["function"]["name"],
                          "args": args if isinstance(args, dict) else {}})
        text = m.get("content") or ""
        if isinstance(text, list):  # réponse découpée en morceaux
            text = "".join(p.get("text", "") for p in text if isinstance(p, dict))
        return {"role": "assistant", "text": text.strip(), "calls": calls}, data.get("usage", {}).get("total_tokens", 0)


# ---------------------------------------------------------------------------- Routeur
DEFAULT_MODELS = {
    "gemini": ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.7-flash", "gemini-3-flash-preview",
               "gemini-3.1-flash-lite"],
    "groq": ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"],
    "mistral": ["mistral-medium-latest", "mistral-small-latest", "mistral-large-latest"],
}
# Quand le fournisseur d'une IA est saturé : à qui demander ensuite (Groq, le plus chargé, en dernier)
FALLBACK = {"gemini": ("mistral", "groq"), "groq": ("mistral", "gemini"), "mistral": ("gemini", "groq")}
RELAY_KEY = 2  # 3e clé de chaque fournisseur : relais (et recherche web pour Gemini)


class Router:
    def __init__(self, cfg):
        self.providers = {"gemini": Gemini(cfg.gemini_keys), "groq": Groq(cfg.groq_keys),
                          "mistral": Mistral(getattr(cfg, "mistral_keys", []) or [])}
        self.usage = defaultdict(lambda: {"tokens": 0, "appels": 0})  # par IA
        self.slots = defaultdict(lambda: {"tokens": 0, "appels": 0})  # par clé
        self._lock = threading.Lock()
        self._searches: dict = {}  # recherches web déjà faites pendant la séance (même question = même réponse)
        self._search_turn = 0  # les recherches tournent sur les 3 clés Gemini
        # (fournisseur, clé, modèle) -> heure avant laquelle on ne le réessaie pas : un modèle qui demande
        # d'attendre 30 minutes n'est plus réessayé à chaque tour de chaque IA.
        self._cool: dict = {}
        # (fournisseur, modèle) -> plus petite taille de requête (en caractères) refusée comme trop grosse
        self._too_big: dict = {}

    # -- mémoire des quotas entre les séances (memoire/quotas.json)
    def load_quotas(self, data: dict) -> int:
        """Reprend les modèles saturés lors des séances précédentes : on ne les réessaie pas pour rien."""
        now, n = time.time(), 0
        for k, until in (data.get("satures") or {}).items():
            prov, ki, model = k.split("|", 2)
            if float(until) > now and prov in self.providers:
                self._cool_down(prov, int(ki), model, float(until) - now)
                n += 1
        return n

    def export_quotas(self) -> dict:
        """Les saturations longues (plus de 10 minutes) à garder pour les prochaines séances."""
        now = time.time()
        with self._lock:
            return {f"{p}|{k}|{m}": round(u) for (p, k, m), u in self._cool.items() if u - now > 600}

    def saturated_share(self, agents) -> float:
        """Part des IA dont le modèle principal, sur leur propre clé, est saturé au début de la séance."""
        if not agents:
            return 0.0
        return sum(self._cool_left(a.provider, a.key_index, a.models[0]) > 0 for a in agents) / len(agents)

    def _cool_left(self, prov, ki, model) -> float:
        with self._lock:
            return self._cool.get((prov, ki, model), 0.0) - time.time()

    def _cool_down(self, prov, ki, model, seconds: float):
        with self._lock:
            key = (prov, ki, model)
            self._cool[key] = max(self._cool.get(key, 0.0), time.time() + seconds)

    def _attempts(self, provider: str, key_index: int, models: list[str]):
        """Ordre d'essai : sa clé, la clé relais du même fournisseur, puis les autres fournisseurs."""
        out = []
        own = self.providers[provider]
        keys = [key_index, RELAY_KEY] + [i for i in range(len(own.keys)) if i not in (key_index, RELAY_KEY)]
        for ki in dict.fromkeys(k for k in keys if k < len(own.keys)):
            out += [(provider, ki, m) for m in models]
        for other in FALLBACK[provider]:
            prov = self.providers.get(other)
            for ki in range(len(prov.keys) if prov else 0):
                out += [(other, ki, m) for m in DEFAULT_MODELS[other]]
        return out

    def _record(self, who, prov, ki, tokens):
        with self._lock:
            self.usage[who]["tokens"] += tokens
            self.usage[who]["appels"] += 1
            self.slots[f"{prov}#{ki + 1}"]["tokens"] += tokens
            self.slots[f"{prov}#{ki + 1}"]["appels"] += 1

    def chat(self, agent, system, messages, tools, label=""):
        """Un tour de conversation pour une IA. Renvoie (message assistant, "fournisseur#clé:modèle")."""
        attempts = self._attempts(agent.provider, agent.key_index, agent.models)
        for round_ in range(2):
            try:
                return self._chat_once(agent, system, messages, tools, label, attempts)
            except LLMError as e:
                if isinstance(e, ContextTooLarge) or round_:
                    raise
                # Tout est saturé : si un modèle se libère bientôt, on l'attend une fois.
                wait = min((self._cool_left(p, k, m) for p, k, m in attempts), default=0)
                if not 0 < wait <= 120:
                    raise
                log.info("%s : toutes les clés sont saturées, pause %.0fs", label, wait)
                time.sleep(wait + random.uniform(1, 3))

    def _chat_once(self, agent, system, messages, tools, label, attempts):
        last, too_large = None, False
        skipped: set = set()
        cooling = 0
        size = len(system) + len(json.dumps(messages, ensure_ascii=False, default=str)) + len(json.dumps(tools or [], ensure_ascii=False))
        for prov_name, ki, model in attempts:
            prov = self.providers[prov_name]
            if (prov_name, ki) in skipped:
                continue
            if self._cool_left(prov_name, ki, model) > 0:
                cooling += 1
                continue
            if size >= self._too_big.get((prov_name, model), float("inf")) * 0.95:
                too_large = True  # déjà refusée plus petite : inutile de réessayer ce modèle
                continue
            try:
                if model not in prov.available(prov.keys[ki]):
                    continue
            except LLMError as e:  # clé invalide : on passe à la suivante
                last = e
                skipped.add((prov_name, ki))
                continue
            for attempt in range(2):
                try:
                    msg, tokens = prov.chat(prov.keys[ki], model, system, messages, tools)
                    self._record(agent.id, prov_name, ki, tokens)
                    return msg, f"{prov_name}#{ki + 1}:{model}"
                except ContextTooLarge as e:  # trop gros pour ce modèle : le suivant (Gemini accepte bien plus)
                    last, too_large = e, True
                    with self._lock:
                        self._too_big[(prov_name, model)] = min(size, self._too_big.get((prov_name, model), size))
                    break
                except RateLimited as e:
                    last = e
                    if attempt == 0 and e.wait <= 65:
                        log.info("%s : %s#%d %s limité, pause %.0fs", label, prov_name, ki + 1, model, e.wait)
                        time.sleep(e.wait + random.uniform(1, 3))
                        continue
                    self._cool_down(prov_name, ki, model, max(e.wait, 60))
                    break
                except ModelUnavailable as e:  # surcharge passagère (503) : on le laisse souffler un peu
                    last = e
                    self._cool_down(prov_name, ki, model, 60)
                    break
                except (LLMError, requests.RequestException, KeyError, ValueError) as e:
                    last = e
                    if attempt == 0:
                        time.sleep(2)
                        continue
                    break
            log.warning("%s : %s#%d %s indisponible (%s), essai suivant", label, prov_name, ki + 1, model, last)
        if too_large:  # l'IA raccourcira sa conversation et réessaiera
            raise ContextTooLarge(f"{label} : conversation trop longue pour les modèles disponibles")
        raise LLMError(f"{label} : aucune clé ni aucun modèle disponible ({last or f'{cooling} modèle(s) saturé(s)'})")

    def web_search(self, question: str, who: str = "web"):
        """Recherche web, du meilleur au plus simple : Google via Gemini (réponse rédigée et sourcée),
        puis Tavily si une clé est configurée, puis Google Actualités et Wikipédia (sans clé)."""
        from . import tools  # import tardif : tools n'a pas besoin du routeur

        cache_key = " ".join(re.findall(r"\w+", question.lower()))
        with self._lock:
            hit = self._searches.get(cache_key)
            start, self._search_turn = self._search_turn, self._search_turn + 1
        if hit:
            return {**hit, "cache": True, "info": "question déjà posée par l'équipe pendant cette séance : réponse gardée en mémoire"}
        res, why = self._gemini_search(question, who, start), []
        if res is None:
            why.append("Gemini indisponible (quota gratuit atteint ou surcharge)")
        if res is None and tools.tavily_configured():
            try:
                res = {**tools.tavily_search(question), "moteur": "Tavily"}
            except (ValueError, requests.RequestException) as e:
                why.append(f"Tavily : {e}"[:80])
                log.info("recherche web Tavily : %s", e)
        if res is None:
            free = tools.free_search(question)
            if "erreur" not in free:
                res = {**free, "moteur": "Google Actualités + Wikipédia (sans clé)"}
            else:
                why.append(free["erreur"])
        if res is None:
            return {"erreur": f"Recherche web indisponible ({' ; '.join(why)}). Note l'information comme inconnue et avance."}
        with self._lock:
            self._searches[cache_key] = res
        return dict(res)

    def _gemini_search(self, question: str, who: str, start: int) -> dict | None:
        """Recherche Google par l'ancrage de Gemini, en faisant tourner les 3 clés. None si indisponible :
        un quota épuisé n'est pas réessayé avant la fin de son délai (pas de pause, on passe au secours)."""
        gem = self.providers["gemini"]
        n = len(gem.keys)
        for ki in [(start + i) % n for i in range(n)]:
            for model in DEFAULT_MODELS["gemini"][:3]:
                if self._cool_left("gemini-recherche", ki, model) > 0:
                    continue
                try:
                    if model not in gem.available(gem.keys[ki]):
                        continue
                    text, sources, tokens = gem.search(gem.keys[ki], model, question)
                    self._record(who, "gemini", ki, tokens)
                    return {"reponse": text[:1800], "sources": sources, "moteur": "Google (via Gemini)"}
                except RateLimited as e:
                    self._cool_down("gemini-recherche", ki, model, max(e.wait, 60))
                except ModelUnavailable:
                    self._cool_down("gemini-recherche", ki, model, 60)
                except (LLMError, requests.RequestException) as e:
                    log.info("recherche web : %s", e)
        return None
