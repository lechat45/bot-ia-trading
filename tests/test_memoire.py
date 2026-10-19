"""Tests de la mémoire longue (leçons) et de l'archivage des séances. Lancer : python tests/test_memoire.py"""
import json
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot import memory  # noqa: E402

TMP = Path(tempfile.mkdtemp())
memory.ROOT = TMP  # les tests n'écrivent jamais dans la vraie mémoire


def test_lecons_du_bilan():
    texte = ("1. Résultat : +1,2 %\n4. Leçons\n**LEÇON : ne jamais renforcer une position la veille de ses résultats**\n"
             "Leçon 2 : couper vite une position dont la thèse est cassée\n- leçon : trop court\nLEÇON : x")
    assert memory.lecons_du_bilan(texte) == ["ne jamais renforcer une position la veille de ses résultats",
                                             "couper vite une position dont la thèse est cassée"]


def test_lecons_sans_doublon_et_limitees():
    memory.add_lecons([{"date": "2026-10-16", "auteur": "gerant", "texte": "Garder 10 % de liquidités avant la Fed."}])
    memory.add_lecons([{"date": "2026-10-19", "auteur": "qualite", "texte": "garder 10 % de liquidités avant la Fed"}])
    assert len(memory.read_lecons()) == 1
    memory.add_lecons([{"date": "2026-10-19", "auteur": "bilan", "texte": f"Leçon numéro {i}"} for i in range(60)])
    lecons = memory.read_lecons()
    assert len(lecons) == memory.MAX_LECONS and lecons[-1]["texte"] == "Leçon numéro 59"


def test_archivage_des_seances():
    folder = TMP / "sessions"
    folder.mkdir(parents=True, exist_ok=True)
    names = [f"2026-09-{d:02d}_0900_preparation" for d in range(1, 29)] + ["2026-10-01_0900_preparation"]
    for n in names:
        (folder / f"{n}.json").write_text(json.dumps({"nom": n}), encoding="utf-8")
        (folder / f"{n}.md").write_text(f"# {n}", encoding="utf-8")
    assert memory.archive_sessions(keep=5) == len(names) - 5
    kept = sorted(p.stem for p in folder.glob("*.json"))
    assert kept == sorted(names)[-5:]  # les plus récentes restent
    with zipfile.ZipFile(TMP / "archives" / "seances-2026-09.zip") as z:
        assert f"{names[0]}.json" in z.namelist() and f"{names[0]}.md" in z.namelist()
    assert memory.archive_sessions(keep=5) == 0  # rien de plus à ranger


def test_alerte_une_seule_fois_par_jour():
    assert memory.alert_once("2026-10-20", "preparation")
    assert not memory.alert_once("2026-10-20", "preparation")  # les rattrapages ne repréviennent pas
    assert memory.alert_once("2026-10-20", "ouverture") and memory.alert_once("2026-10-21", "preparation")


def test_seance_manquee():
    import datetime as dt
    import main
    from bot import notify

    sent = []
    notify.send = lambda titre, message, **kw: sent.append(message)
    now = dt.datetime(2026, 10, 22, 13, 25, tzinfo=dt.timezone.utc)  # jeudi, avant l'ouverture
    clock = {"is_open": False, "next_open": "2026-10-22T09:30:00-04:00"}
    memory.write_plan({"date": "2026-10-21", "ordres": []})  # plan de la veille : la préparation a sauté
    main.check_missed(clock, "ouverture", now)
    main.check_missed(clock, "ouverture", now)  # rattrapage suivant : pas de 2e notification
    assert len(sent) == 1 and "préparation" in sent[0]
    memory.write_plan({"date": "2026-10-22", "ordres": [{"statut": "en_attente"}]})
    main.check_missed({"is_open": True}, "suivi", now.replace(hour=17))  # ordres jamais exécutés
    assert len(sent) == 2 and "pas été exécutés" in sent[1]
    main.check_missed({"is_open": False, "next_open": "2026-10-26T09:30:00-04:00"}, "suivi", now)  # pas un jour de bourse
    assert len(sent) == 2


def test_registre_des_propositions():
    memory.append_propositions([{"date": "2026-10-19", "id": "qualite-1", "auteur": "qualite", "action": "acheter",
                                 "symbole": "AAPL", "prix_ref": 200, "retenue": True, "verdict": "ok"}])
    assert memory.read_propositions()[-1]["symbole"] == "AAPL"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("OK", name)
