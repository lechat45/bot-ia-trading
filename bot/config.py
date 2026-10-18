"""Configuration lue depuis les variables d'environnement (ou le fichier .env en local)."""
import os
from dataclasses import dataclass, field

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


def _list(name: str, default: list[str]) -> list[str]:
    v = os.getenv(name, "").strip()
    return [x.strip() for x in v.split(",") if x.strip()] if v else default


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
    gemini_models: list[str] = field(default_factory=list)
    groq_models: list[str] = field(default_factory=list)
    # Limites de risque appliquées par le code (les IA ne peuvent pas les contourner)
    max_position_pct: float = 10.0  # % max du portefeuille par titre
    min_cash_pct: float = 10.0  # % de cash toujours conservé
    max_positions: int = 12
    max_orders: int = 4  # ordres max par session
    max_stop_distance_pct: float = 15.0  # stop au plus à 15 % sous le prix
    min_stop_distance_pct: float = 1.0  # stop pas trop collé au prix
    min_reward_risk: float = 1.5  # gain visé / perte max
    anti_churn_days: int = 2  # pas de rachat d'un titre vendu il y a moins de N jours
    min_price: float = 5.0  # pas de penny stocks

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
            gemini_models=_list(
                "GEMINI_MODELS",
                ["gemini-3.5-flash", "gemini-3-flash", "gemini-3-flash-preview",
                 "gemini-2.5-flash", "gemini-3.1-flash-lite", "gemini-2.5-flash-lite"],
            ),
            groq_models=_list(
                "GROQ_MODELS",
                ["openai/gpt-oss-120b", "llama-3.3-70b-versatile", "qwen/qwen3-32b",
                 "openai/gpt-oss-20b", "llama-3.1-8b-instant"],
            ),
            max_position_pct=_float("MAX_POSITION_PCT", 10.0),
            min_cash_pct=_float("MIN_CASH_PCT", 10.0),
            max_positions=int(_float("MAX_POSITIONS", 12)),
            max_orders=int(_float("MAX_ORDERS_PER_SESSION", 4)),
            max_stop_distance_pct=_float("MAX_STOP_DISTANCE_PCT", 15.0),
            min_reward_risk=_float("MIN_REWARD_RISK", 1.5),
        )

    def problems(self) -> list[str]:
        p = []
        if self.live_refused:
            p.append(
                "ALPACA_PAPER=false mais LIVE_TRADING_CONFIRMATION n'est pas renseigné : "
                "refus de trader en argent réel."
            )
        if not self.alpaca_key or not self.alpaca_secret:
            p.append("ALPACA_API_KEY / ALPACA_SECRET_KEY manquantes.")
        if not self.gemini_keys and not self.groq_keys:
            p.append("Aucune clé GEMINI_API_KEY_n ni GROQ_API_KEY_n.")
        return p
