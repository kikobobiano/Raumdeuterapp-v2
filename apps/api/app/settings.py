from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_data_dir() -> Path:
    """Repo: apps/api/app/settings.py → parents[3] is monorepo root. Docker: /app/app → use /app."""
    p = Path(__file__).resolve()
    if len(p.parents) > 3:
        return p.parents[3] / "data"
    return p.parents[1] / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="RAUMDEUTER_")

    # default_factory so import does not evaluate parents[3] before env is applied (Docker has shorter path)
    data_dir: Path = Field(default_factory=_default_data_dir)
    cors_origins: list[str] = ["http://localhost:3000"]


settings = Settings()
