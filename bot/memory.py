"""Mémoire persistante : notes de chaque IA (l'outil « Notes » d'Aywen), plan d'ouverture, journal,
rapports de séance et état en direct. Le dossier memoire/ est recommité par GitHub Actions."""
import datetime as dt
import json
import re
import threading
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "memoire"
MAX_NOTES = 3500
MAX_LECONS = 40  # leçons gardées dans la mémoire longue de l'équipe
KEEP_SESSIONS = 60  # séances gardées telles quelles, les plus anciennes vont dans memoire/archives/
_lock = threading.Lock()


def _write(p: Path, text: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _read_json(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


# ---------------------------------------------------------------------- notes
def read_notes(agent: str) -> str:
    p = ROOT / "notes" / f"{agent}.md"
    return p.read_text(encoding="utf-8")[-MAX_NOTES:] if p.exists() else ""


def write_notes(agent: str, text: str, when: str) -> None:
    if text and text.strip():
        _write(ROOT / "notes" / f"{agent}.md", f"_Mis à jour : {when}_\n\n{text.strip()[:MAX_NOTES]}\n")


# ---------------------------------------------------------------------- plan d'ouverture
def plan_path(simulation: bool) -> Path:
    return ROOT / ("plan_simulation.json" if simulation else "plan.json")


def read_plan(simulation: bool = False) -> dict:
    return _read_json(plan_path(simulation), {})


def write_plan(plan: dict, simulation: bool = False) -> None:
    _write(plan_path(simulation), json.dumps(plan, ensure_ascii=False, indent=1))


# ---------------------------------------------------------------------- rappels
def read_rappels() -> list[dict]:
    """Rappels créés par les IA (un événement daté à ne pas oublier : résultats, annonce, réunion…)."""
    return _read_json(ROOT / "rappels.json", [])


def write_rappels(rappels: list[dict]) -> None:
    _write(ROOT / "rappels.json", json.dumps(rappels, ensure_ascii=False, indent=1))


# ---------------------------------------------------------------------- bilans de la semaine
def write_bilan(date: str, texte: str) -> None:
    _write(ROOT / "bilans" / f"{date}.md", texte.strip() + "\n")


def read_last_bilan() -> dict:
    files = sorted((ROOT / "bilans").glob("*.md")) if (ROOT / "bilans").exists() else []
    return {"date": files[-1].stem, "texte": files[-1].read_text(encoding="utf-8")} if files else {}


# ---------------------------------------------------------------------- leçons (mémoire longue)
def read_lecons() -> list[dict]:
    return _read_json(ROOT / "lecons.json", [])


def add_lecons(items: list[dict]) -> None:
    """Ajoute des leçons ({date, auteur, texte}) ; une leçon déjà connue n'est pas dupliquée."""
    if not items:
        return
    with _lock:
        cur = read_lecons()
        known = {re.sub(r"\W+", " ", l["texte"].lower()).strip() for l in cur}
        for it in items:
            k = re.sub(r"\W+", " ", it["texte"].lower()).strip()
            if k and k not in known:
                cur.append(it)
                known.add(k)
        _write(ROOT / "lecons.json", json.dumps(cur[-MAX_LECONS:], ensure_ascii=False, indent=1))


def lecons_du_bilan(texte: str) -> list[str]:
    """Les lignes « LEÇON : … » écrites par le gérant à la fin du bilan de la semaine."""
    out = []
    for line in texte.splitlines():
        m = re.match(r"^\W*le[çc]on\s*\d*\s*[:：-]\s*(.+)$", line.strip(), re.I)
        if m and len(m.group(1)) > 10:
            out.append(m.group(1).strip().strip("*").strip()[:300])
    return out[:3]


# ---------------------------------------------------------------------- propositions (classement des analystes)
def append_propositions(rows: list[dict]) -> None:
    """Garde chaque proposition des analystes (prix du jour, avis, retenue ou non) pour mesurer après coup
    ce qu'elle aurait rapporté, même quand la séance a été archivée."""
    if not rows:
        return
    with _lock:
        p = ROOT / "propositions.jsonl"
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")


def read_propositions() -> list[dict]:
    p = ROOT / "propositions.jsonl"
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


# ---------------------------------------------------------------------- vérification de l'installation
def read_installation() -> dict:
    return _read_json(ROOT / "installation.json", {})


def write_installation(data: dict) -> None:
    _write(ROOT / "installation.json", json.dumps(data, ensure_ascii=False, indent=1))


# ---------------------------------------------------------------------- journal
def append_journal(entries: list[dict]) -> None:
    if not entries:
        return
    with _lock:
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


# ---------------------------------------------------------------------- séances
def write_report(name: str, markdown: str) -> Path:
    p = ROOT / "sessions" / f"{name}.md"
    _write(p, markdown)
    return p


def write_session_json(name: str, data: dict) -> None:
    _write(ROOT / "sessions" / f"{name}.json", json.dumps(data, ensure_ascii=False, indent=1, default=str))


def archive_sessions(keep: int = KEEP_SESSIONS) -> int:
    """Range les séances les plus anciennes dans memoire/archives/seances-AAAA-MM.zip (le nom des
    séances commence par leur date). Renvoie le nombre de séances archivées."""
    folder = ROOT / "sessions"
    if not folder.exists():
        return 0
    names = sorted({p.stem for p in folder.iterdir() if p.suffix in (".json", ".md")})
    old = names[:-keep] if keep else names
    for name in old:
        month = name[:7] if re.match(r"^\d{4}-\d{2}", name) else "autres"
        z = ROOT / "archives" / f"seances-{month}.zip"
        z.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(z, "a", zipfile.ZIP_DEFLATED) as zf:
            have = set(zf.namelist())
            for ext in (".json", ".md"):
                f = folder / f"{name}{ext}"
                if f.exists():
                    if f.name not in have:
                        zf.write(f, f.name)
                    f.unlink()
    return len(old)


def append_history(rows: list[dict]) -> None:
    """Valeur de chaque sous-compte après chaque séance (courbes du tableau de bord)."""
    p = ROOT / "historique_ia.csv"
    new = not p.exists()
    with p.open("a", encoding="utf-8") as f:
        if new:
            f.write("date,agent,valeur,cash,positions\n")
        for r in rows:
            f.write(f"{r['date']},{r['agent']},{r['valeur']},{r['cash']},{r['positions']}\n")


def read_history() -> list[dict]:
    p = ROOT / "historique_ia.csv"
    if not p.exists():
        return []
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines()[1:]:
        parts = line.split(",")
        if len(parts) == 5:
            rows.append({"date": parts[0], "agent": parts[1], "valeur": float(parts[2]),
                         "cash": float(parts[3]), "positions": int(parts[4])})
    return rows


# ---------------------------------------------------------------------- état en direct
_state: dict = {}


def state_start(mode: str, simulation: bool, agents: list[str]) -> None:
    global _state
    with _lock:
        _state = {"running": True, "mode": mode, "simulation": simulation,
                  "debut": dt.datetime.now(dt.timezone.utc).isoformat(),
                  "agents": {a: {"statut": "attente", "action": "", "etapes": 0} for a in agents}}
        _flush()


def state_agent(agent: str, **kw) -> None:
    with _lock:
        if _state:
            _state.setdefault("agents", {}).setdefault(agent, {}).update(kw)
            _flush()


def state_stop() -> None:
    with _lock:
        if _state:
            _state["running"] = False
            _flush()


def _flush():
    _state["maj"] = dt.datetime.now(dt.timezone.utc).isoformat()
    _write(ROOT / "etat.json", json.dumps(_state, ensure_ascii=False))
