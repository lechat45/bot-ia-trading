"""Configuration lue depuis les variables d'environnement (ou le fichier .env en local)."""
import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# Phrase exacte à mettre dans LIVE_TRADING_CONFIRMATION pour autoriser l'argent réel.
LIVE_CONFIRMATION = "JE_COMPRENDS_LES_RISQUES"


def _bool(name: str, default: bool) -> bool:
    v = os.getenv(name, "").strip().lower()
    if not v:
        return default
    return v in ("1", "true", "yes", "oui", "on")


def _float(name: str, default: float) -> float:
    v = os.getenv(name, "").strip()
    return float(v) if v else default


def _keys(prefix: str) -> list[str]:
    return [k for k in (os.getenv(f"{prefix}_{i}", "").strip() for i in (1, 2, 3)) if k]


@dataclass
class Config:
    gemini_keys: list[str]
    groq_keys: list[str]
    alpaca_key: str
    alpaca_secret: str
    paper: bool
    live_refused: bool  # ALPACA_PAPER=false demandé sans la phrase de confirmation
    dry_run: bool
    # Limites appliquées par le code au compte de l'équipe (les IA ne peuvent pas les contourner)
    max_position_pct: float = 15.0  # % max du compte sur un même titre
    min_cash_pct: float = 5.0  # % du compte toujours gardé en liquidités
    max_positions: int = 10
    max_orders: int = 5  # ordres max du gérant par séance
    max_stop_distance_pct: float = 15.0
    min_stop_distance_pct: float = 1.0
    min_reward_risk: float = 1.5  # gain visé / perte max
    anti_churn_days: int = 2  # pas de rachat d'un titre vendu il y a moins de N jours
    min_price: float = 5.0  # pas de penny stocks
    max_gap_pct: float = 5.0  # ordre planifié annulé si l'ouverture s'écarte trop du prix du matin
    max_sector_pct: float = 35.0  # % max du compte dans un même secteur (tech, énergie…)
    earnings_blackout_days: int = 1  # pas d'achat si les résultats tombent dans 0 ou 1 jour
    frein_jour_pct: float = 3.0  # frein d'urgence : plus d'achat si le compte perd 3 % en un jour…
    frein_semaine_pct: float = 7.0  # … ou 7 % sur 7 jours
    # Stop suiveur codé : à +5 % le stop remonte au prix d'achat, à +10 % il suit le cours à 5 % en dessous
    stop_suiveur_pct: float = 5.0  # 0 = désactivé
    stop_suiveur_distance_pct: float = 5.0
    # Séances
    preparation_heure: int = 9  # heure de Paris de la séance de préparation
    # Appels d'outils max par IA et par séance (les clés gratuites limitent le débit)
    max_steps_analyste: int = 10
    max_steps_analyste_suivi: int = 6
    max_steps_critique: int = 6
    max_steps_gerant: int = 12
    max_steps_gerant_leger: int = 8  # séance de suivi allégée (rien de notable : le gérant seul)
    suivi_complet: bool = False  # True : toute l'équipe à chaque suivi, même sans événement
    suivi_mouvement_pct: float = 4.0  # une position qui bouge de 4 % dans la journée réveille l'équipe
    suivi_marche_pct: float = 1.5  # … de même si le S&P 500 bouge de 1,5 %
    max_web_searches: int = 3  # recherches Google par IA et par séance

    @classmethod
    def from_env(cls) -> "Config":
        want_live = not _bool("ALPACA_PAPER", True)
        confirmed = os.getenv("LIVE_TRADING_CONFIRMATION", "").strip() == LIVE_CONFIRMATION
        return cls(
            gemini_keys=_keys("GEMINI_API_KEY"),
            groq_keys=_keys("GROQ_API_KEY"),
            alpaca_key=os.getenv("ALPACA_API_KEY", "").strip(),
            alpaca_secret=os.getenv("ALPACA_SECRET_KEY", "").strip(),
            paper=not (want_live and confirmed),
            live_refused=want_live and not confirmed,
            dry_run=_bool("DRY_RUN", False),
            max_position_pct=_float("MAX_POSITION_PCT", 15.0),
            min_cash_pct=_float("MIN_CASH_PCT", 5.0),
            max_positions=int(_float("MAX_POSITIONS", 10)),
            max_orders=int(_float("MAX_ORDERS_PER_SESSION", 5)),
            max_stop_distance_pct=_float("MAX_STOP_DISTANCE_PCT", 15.0),
            min_reward_risk=_float("MIN_REWARD_RISK", 1.5),
            max_gap_pct=_float("MAX_GAP_PCT", 5.0),
            max_sector_pct=_float("MAX_SECTOR_PCT", 35.0),
            frein_jour_pct=_float("FREIN_JOUR_PCT", 3.0),
            frein_semaine_pct=_float("FREIN_SEMAINE_PCT", 7.0),
            stop_suiveur_pct=_float("STOP_SUIVEUR_PCT", 5.0),
            stop_suiveur_distance_pct=_float("STOP_SUIVEUR_DISTANCE_PCT", 5.0),
            suivi_complet=_bool("SUIVI_COMPLET", False),
            preparation_heure=int(_float("PREPARATION_HEURE", 9)),
            max_steps_analyste=int(_float("MAX_STEPS_ANALYSTE", 10)),
            max_steps_analyste_suivi=int(_float("MAX_STEPS_ANALYSTE_SUIVI", 6)),
            max_steps_critique=int(_float("MAX_STEPS_CRITIQUE", 6)),
            max_steps_gerant=int(_float("MAX_STEPS_GERANT", 12)),
            max_web_searches=int(_float("MAX_WEB_SEARCHES", 3)),
        )

    def problems(self) -> list[str]:
        p = []
        if self.live_refused:
            p.append("ALPACA_PAPER=false mais LIVE_TRADING_CONFIRMATION n'est pas renseigné : "
                     "refus de trader en argent réel.")
        if not self.alpaca_key or not self.alpaca_secret:
            p.append("ALPACA_API_KEY / ALPACA_SECRET_KEY manquantes.")
        if not self.gemini_keys and not self.groq_keys:
            p.append("Aucune clé GEMINI_API_KEY_n ni GROQ_API_KEY_n.")
        return p
