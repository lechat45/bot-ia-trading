"""Tests des skills : fiches présentes, renvois valides, consignes de taille raisonnable.
Lancer : python tests/test_skills.py"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.agent_tools import SKILL_INFO, declarations  # noqa: E402
from bot.agents import AGENTS, Session  # noqa: E402
from bot.config import Config  # noqa: E402

SKILLS = Path(__file__).resolve().parent.parent / "skills"
MAX_CONSIGNES = 10_000  # caractères envoyés à chaque appel d'une IA : au-delà, les quotas gratuits souffrent


def test_toutes_les_fiches_existent():
    for nom in SKILL_INFO:
        assert (SKILLS / "commun" / f"{nom}.md").exists(), nom
    for a in AGENTS:
        assert (SKILLS / "strategies" / f"{a.strategie}.md").exists(), a.strategie


def test_les_renvois_entre_fiches_sont_valides():
    connues = set(SKILL_INFO)
    for f in list((SKILLS / "commun").glob("*.md")) + list((SKILLS / "strategies").glob("*.md")):
        for nom in re.findall(r"fiches? ([a-z]+(?:-[a-z]+)+)", f.read_text(encoding="utf-8")):
            assert nom in connues, f"{f.name} renvoie à la fiche inconnue « {nom} »"


def test_les_outils_cites_existent():
    outils = {d["name"] for role in ("analyste", "critique", "gerant") for d in declarations(role, False)}
    for f in list((SKILLS / "commun").glob("*.md")) + list((SKILLS / "strategies").glob("*.md")):
        for nom in re.findall(r"\b([a-z]+_[a-z_]+)\(", f.read_text(encoding="utf-8")):
            assert nom in outils, f"{f.name} cite l'outil inconnu « {nom} »"


def test_taille_des_consignes():
    cfg = Config(gemini_keys=[], groq_keys=[], alpaca_key="", alpaca_secret="", paper=True, live_refused=False,
                 dry_run=True)
    s = Session(cfg, None, None, "preparation", True)
    s.market_open = False
    for a in AGENTS:
        n = len(s.system_prompt(a))
        assert n <= MAX_CONSIGNES, f"consignes de {a.id} trop longues : {n} caractères"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("OK", name)
