"""Génère la version EN LIGNE (statique) du tableau de bord dans site/.

GitHub Actions l'exécute après chaque session puis publie site/ sur GitHub Pages (dépôt public)
ou Cloudflare Pages (dépôt privé). Aucune clé n'est écrite dans site/ : seulement les chiffres
du compte, les positions, les sessions et les notes des agents.

    python build_site.py      puis ouvrir site/index.html via un petit serveur
"""
import datetime as dt
import json
import os
import shutil
from pathlib import Path

import dashboard as d

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "site"


def dump(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, default=str), encoding="utf-8")


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "data" / "sessions").mkdir(parents=True)
    for f in ("style.css", "app.js"):
        shutil.copy(d.WEB / f, OUT / f)
    html = (d.WEB / "index.html").read_text(encoding="utf-8")
    html = html.replace('<script src="app.js"></script>',
                        '<script>window.STATIC_SITE = true;</script>\n  <script src="app.js"></script>')
    (OUT / "index.html").write_text(html, encoding="utf-8")

    ov = d.overview()
    repo = os.getenv("GITHUB_REPOSITORY")
    ov["genere_le"] = dt.datetime.now(dt.timezone.utc).isoformat()
    ov["actions_url"] = (f"{os.getenv('GITHUB_SERVER_URL', 'https://github.com')}/{repo}"
                         "/actions/workflows/trading.yml") if repo else None
    dump(OUT / "data" / "overview.json", ov)
    sessions = d.sessions()
    dump(OUT / "data" / "sessions.json", sessions)
    for s in sessions:
        src = d.MEM / "sessions" / f"{s['nom']}.json"
        shutil.copy(src, OUT / "data" / "sessions" / src.name)
    dump(OUT / "data" / "notes.json", d.notes())
    dump(OUT / "data" / "state.json", d.state())
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    print(f"Site généré dans {OUT} ({len(sessions)} session(s))")


if __name__ == "__main__":
    main()
