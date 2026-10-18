"""Lance UNE session de trading (GitHub Actions en lance 2 par jour, comme Aywen).

    python main.py               session normale (paper trading par défaut)
    python main.py --dry-run     les IA réfléchissent mais aucun ordre n'est envoyé
    python main.py --force       tourne même si la bourse est fermée (utile avec --dry-run)
    python main.py --offline     test complet sans clés ni réseau (fausses données)
"""
import argparse
import logging
import sys

from bot.agents import Session
from bot.config import Config


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)-9s %(message)s",
                        datefmt="%H:%M:%S", stream=sys.stdout)
    log = logging.getLogger("main")
    cfg = Config.from_env()

    if args.offline:
        from bot.fakes import FakeAlpaca, FakeRouter

        cfg.paper = True
        alpaca, router, dry_run = FakeAlpaca(), FakeRouter(), True
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

    log.info("Mode %s%s — %d clé(s) Gemini, %d clé(s) Groq",
             "PAPER" if cfg.paper else "ARGENT RÉEL", " / SIMULATION" if dry_run else "",
             len(cfg.gemini_keys), len(cfg.groq_keys))
    clock = alpaca.clock()
    if not clock.get("is_open") and not args.force:
        log.info("Bourse de New York fermée (prochaine ouverture %s) : rien à faire.", clock.get("next_open"))
        return 0
    if not clock.get("is_open") and not dry_run:
        log.info("Bourse fermée + --force : passage forcé en simulation.")
        dry_run = True

    results, rejected = Session(cfg, alpaca, router, dry_run, offline=args.offline).run()
    log.info("Terminé : %d ordre(s) traité(s), %d rejeté(s).", len(results), len(rejected))
    return 0


if __name__ == "__main__":
    sys.exit(main())
