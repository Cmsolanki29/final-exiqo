"""Centralised settings loaded from environment variables via pydantic-settings.

Phase 1: Real-time event-driven scoring.
All tunable parameters live here so nothing is hardcoded across the codebase.
When ENV=prod, missing required vars raise an error at startup rather than at
the first request — fail-fast is intentional.

Performance budget: this module is imported once at startup; no runtime cost.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import quote_plus

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env early so individual env vars are visible to pydantic-settings.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=_PROJECT_ROOT / ".env", override=False)


class Settings(BaseSettings):
    """Application settings.  Loaded once and cached via get_settings()."""

    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------ #
    # Environment
    # ------------------------------------------------------------------ #
    ENV: Literal["dev", "staging", "prod"] = "dev"

    # ------------------------------------------------------------------ #
    # Database — asyncpg (new Phase 1 path)
    # Falls back to constructing from individual vars if DATABASE_URL absent.
    # ------------------------------------------------------------------ #
    DATABASE_URL: str = Field(default="")
    DB_HOST: str = Field(default="127.0.0.1")
    DB_PORT: int = Field(default=5432)
    DB_NAME: str = Field(default="smartspend_db")
    DB_USER: str = Field(default="postgres")
    DB_PASSWORD: str = Field(default="")

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _build_database_url(cls, v: str) -> str:
        """Construct asyncpg-compatible DSN from individual vars when DATABASE_URL is absent."""
        if v:
            return v
        host = os.getenv("DB_HOST", "127.0.0.1")
        port = os.getenv("DB_PORT", "5432")
        name = os.getenv("DB_NAME", "smartspend_db")
        user = os.getenv("DB_USER", "postgres")
        password = os.getenv("DB_PASSWORD", "").strip('"').strip("'")
        # URL-encode password so special chars like @ # % don't break the DSN
        return f"postgresql://{quote_plus(user)}:{quote_plus(password)}@{host}:{port}/{name}"

    # ------------------------------------------------------------------ #
    # Redis
    # ------------------------------------------------------------------ #
    REDIS_URL: str = "redis://localhost:6379/0"

    # ------------------------------------------------------------------ #
    # MLflow
    # ------------------------------------------------------------------ #
    MLFLOW_TRACKING_URI: str = "sqlite:///mlflow.db"

    # ------------------------------------------------------------------ #
    # Risk thresholds
    # ------------------------------------------------------------------ #
    RISK_BLOCK_THRESHOLD: int = 85
    RISK_CHALLENGE_THRESHOLD: int = 65
    RISK_REVIEW_THRESHOLD: int = 40

    # ------------------------------------------------------------------ #
    # Ensemble weights (unsupervised / supervised blend)
    # ------------------------------------------------------------------ #
    UNSUP_WEIGHT: float = 0.30
    SUP_WEIGHT: float = 0.70

    # ------------------------------------------------------------------ #
    # Feature store
    # ------------------------------------------------------------------ #
    FEATURE_TTL_SEC: int = 86400        # 24 h online store TTL
    BASELINE_TTL_SEC: int = 3600 * 72  # 3-day user baseline cache
    MATERIALIZER_INTERVAL_MIN: int = 15

    # ------------------------------------------------------------------ #
    # Alerts
    # ------------------------------------------------------------------ #
    ALERT_COOLDOWN_SEC: int = 600       # 10 min between same alert
    ALERT_HOURLY_CAP: int = 5           # digest mode above this

    # ------------------------------------------------------------------ #
    # MLOps
    # ------------------------------------------------------------------ #
    RETRAIN_SCHEDULE_CRON: str = "0 2 * * 0"  # Sunday 02:00 UTC
    DRIFT_PSI_ALERT_THRESHOLD: float = 0.25
    CANARY_PERCENTAGE: int = 5

    # ------------------------------------------------------------------ #
    # Supervised model
    # ------------------------------------------------------------------ #
    SUPERVISED_MODEL_PATH: str = "models/supervised_v0.pkl"
    SUPERVISED_MIN_TRAIN_LABELS: int = 50   # need at least this many labeled rows

    # ------------------------------------------------------------------ #
    # Performance hard-limit
    # ------------------------------------------------------------------ #
    SCORING_TIMEOUT_MS: int = 500       # Return 503 if exceeded


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached singleton Settings instance."""
    return Settings()
