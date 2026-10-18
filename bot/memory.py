"""Mémoire persistante (l'outil « Notes » d'Aywen) : notes par agent, journal, rapports.
Le dossier memoire/ est recommité par GitHub Actions après chaque session."""
import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "memoire"
MAX_NOTES = 3500


def read_notes(agent: str) -> str:
    p = ROOT / "notes" / f"{agent}.md"
    return p.read_text(encoding="utf-8")[-MAX_NOTES:] if p.exists() else "(aucune note : première session)"


def write_notes(agent: str, text: str, when: str) -> None:
    if not text or not text.strip():
        return
    p = ROOT / "notes" / f"{agent}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"_Mis à jour : {when}_\n\n{text.strip()[:MAX_NOTES]}\n", encoding="utf-8")


def append_journal(entries: list[dict]) -> None:
    p = ROOT / "journal.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")


def recent_journal(days: int) -> list[dict]:
    p = ROOT / "journal.jsonl"
    if not p.exists():
        return []
    cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)).isoformat()
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if e.get("ts", "") >= cutoff:
            out.append(e)
    return out


def write_report(name: str, markdown: str) -> Path:
    p = ROOT / "sessions" / f"{name}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(markdown, encoding="utf-8")
    return p


def append_history(row: dict) -> None:
    p = ROOT / "historique.csv"
    new = not p.exists()
    with p.open("a", encoding="utf-8") as f:
        if new:
            f.write(",".join(row) + "\n")
        f.write(",".join(str(v) for v in row.values()) + "\n")


def write_session_json(name: str, data: dict) -> None:
    p = ROOT / "sessions" / f"{name}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


def write_state(state: dict) -> None:
    p = ROOT / "etat.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
