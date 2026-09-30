"""Configuration de l'application, lue depuis l'environnement ou .env."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
PROJECTS_DIR = ROOT / "projects"
CATALOG_PATH = DATA_DIR / "catalog.json"
DB_PATH = DATA_DIR / "coach.db"


class Settings(BaseSettings):
    """Reglages du coach. Aucune valeur sensible n'est codee en dur."""

    anthropic_api_key: str = ""
    coach_model: str = "claude-sonnet-5"
    pass_threshold: float = Field(default=14.0, ge=0.0, le=20.0)
    hint_penalties: tuple[float, float, float] = (0.5, 1.0, 2.0)
    git_remote: str = ""
    git_branch: str = "main"

    model_config = SettingsConfigDict(
        env_file=ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    @field_validator("hint_penalties", mode="before")
    @classmethod
    def _parse_penalties(cls, value: object) -> object:
        """Accepte la forme "0.5,1.0,2.0" utilisee dans le .env."""
        if isinstance(value, str):
            parts = [part.strip() for part in value.split(",") if part.strip()]
            return tuple(float(part) for part in parts)
        return value

    @property
    def llm_ready(self) -> bool:
        return bool(self.anthropic_api_key.strip())

    def penalty_for_level(self, level: int) -> float:
        """Malus du palier d'indice demande (1, 2 ou 3)."""
        if not 1 <= level <= len(self.hint_penalties):
            return 0.0
        return self.hint_penalties[level - 1]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
