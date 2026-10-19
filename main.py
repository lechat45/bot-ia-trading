"""Lance une séance des 4 IA (GitHub Actions s'en charge automatiquement chaque jour de bourse).

    python main.py --mode preparation   9 h : les IA décident quoi acheter à l'ouverture (ordres planifiés)
    python main.py --mode ouverture     attend l'ouverture de New York puis exécute les ordres planifiés
    python main.py --mode suivi         bourse ouverte : les IA font le point et agissent en direct
    python main.py --mode auto          préparation si la bourse est fermée, suivi si elle est ouverte

Options :
    --dry-run   simulation : les IA travaillent mais aucun ordre n'est envoyé et rien n'est enregistré
    --force     ignore les vérifications d'horaire (utile pour tester à n'importe quelle heure)
    --offline   test complet sans clé ni réseau (fausses données, fausses IA)
"""
import argparse
import datetime as dt
import logging
import sys
import time
from zoneinfo import ZoneInfo

from bot import memory
from bot.agents import Session
from bot.config import Config

PARIS, NY = ZoneInfo("Europe/Paris"), ZoneInfo("America/New_York")
log = logging.getLogger("main")


def _ny_date(iso: str | None):
    return dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(NY).date() if iso else None


def wait_for_open(alpaca, max_minutes: int) -> bool:
    end = time.time() + max_minutes * 60
    while True:
        clock = alpaca.clock()
        if clock.get("is_open"):
            return True
        if time.time() > end:
            return False
        log.info("Bourse fermée, ouverture prévue %s : attente…", clock.get("next_open"))
        time.sleep(30)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["auto", "preparation", "ouverture", "suivi"], default="auto")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--attente-max", type=int, default=100, help="minutes d'attente max de l'ouverture")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)-8s %(message)s",
                        datefmt="%H:%M:%S", stream=sys.stdout)
    cfg = Config.from_env()

    if args.offline:
        from bot.fakes import FakeAlpaca, FakeRouter

        cfg.paper = True
        alpaca, router, dry_run = FakeAlpaca(open_=args.mode in ("ouverture", "suivi")), FakeRouter(), True
    else:
        problems = cfg.problems()
        if problems:
            for p in problems:
                log.error(p)
            return 1
        from bot.alpaca import Alpaca
        from bot.llm import Router

        alpaca, router = Alpaca(cfg.alpaca_key, cfg.alpaca_secret, cfg.paper), Router(cfg)
        dry_run = cfg.dry_run or args.dry_run

    clock = alpaca.clock()
    is_open = bool(clock.get("is_open"))
    now = dt.datetime.now(dt.timezone.utc)
    mode = args.mode if args.mode != "auto" else ("suivi" if is_open else "preparation")
    log.info("Séance %s — %s%s — %d clé(s) Gemini, %d clé(s) Groq", mode, "PAPER" if cfg.paper else "ARGENT RÉEL",
             " / SIMULATION" if dry_run else "", len(cfg.gemini_keys), len(cfg.groq_keys))

    if mode == "preparation" and not args.force:
        paris = now.astimezone(PARIS)
        h = paris.hour + paris.minute / 60
        if not cfg.preparation_heure - 0.25 <= h < cfg.preparation_heure + 3:
            log.info("Il est %s à Paris : la préparation se fait vers %d h. Rien à faire.",
                     paris.strftime("%H:%M"), cfg.preparation_heure)
            return 0
        if is_open or _ny_date(clock.get("next_open")) != now.astimezone(NY).date():
            log.info("Pas de séance de bourse aujourd'hui à New York (week-end ou jour férié).")
            return 0
        plan = memory.read_plan()
        if plan.get("date") == now.astimezone(NY).date().isoformat():
            log.info("Le plan du jour est déjà préparé.")
            return 0

    if mode == "ouverture":
        plan = memory.read_plan(simulation=args.offline)
        today = now.astimezone(NY).date().isoformat()
        if not args.force and (plan.get("date") != today or plan.get("execute_le")):
            log.info("Aucun plan à exécuter aujourd'hui (plan du %s, %s).", plan.get("date", "—"),
                     "déjà exécuté" if plan.get("execute_le") else "pas encore exécuté")
            return 0
        if not is_open and not args.force:
            if not wait_for_open(alpaca, args.attente_max):
                log.info("La bourse n'a pas ouvert dans le délai : abandon.")
                return 0
            time.sleep(20)  # laisser passer les premières secondes de cotation
        elif not is_open:
            log.info("Bourse fermée + --force : simulation au dernier prix connu.")
            dry_run = True

    if mode == "suivi" and not is_open:
        if not args.force:
            log.info("Bourse fermée : pas de séance de suivi.")
            return 0
        log.info("Bourse fermée + --force : passage en simulation.")
        dry_run = True

    results = Session(cfg, alpaca, router, mode, dry_run, offline=args.offline).run()
    log.info("Séance terminée (%d IA).", len(results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
