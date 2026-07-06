"""Application configuration.

All runtime configuration is sourced from environment variables (loaded from
a `.env` file via pydantic-settings). Nothing here should be hardcoded
elsewhere in the app -- services should depend on a `Settings` instance
rather than reading `os.environ` directly.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Typed application settings, loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- API keys -----------------------------------------------------
    claude_api_key: str = ""
    tavily_api_key: str = ""
    hunter_api_key: str = ""

    # --- Institution identity ------------------------------------------
    # Shown to Claude for identity verification and used in search queries.
    institution_name: str = "your institution"
    # Addresses at this domain (e.g. "example.edu") are treated as stale --
    # alongside a missing email -- and are eligible for replacement. Leave
    # blank to only replace missing emails.
    stale_email_domain: str = ""

    # --- Processing behavior ------------------------------------------
    worker_count: int = 5
    confidence_threshold: int = 80
    retry_count: int = 3
    cache_expiration_days: int = 30

    # --- Directories (may be relative to PROJECT_ROOT or absolute) ----
    upload_dir: str = "uploads"
    output_dir: str = "output"
    cache_dir: str = "cache"
    log_dir: str = "logs"

    # --- Database -------------------------------------------------------
    database_url: str = "sqlite:///./cache/alumni_agent.db"

    def _resolve(self, raw: str) -> Path:
        path = Path(raw)
        return path if path.is_absolute() else PROJECT_ROOT / path

    @property
    def upload_path(self) -> Path:
        return self._resolve(self.upload_dir)

    @property
    def output_path(self) -> Path:
        return self._resolve(self.output_dir)

    @property
    def cache_path(self) -> Path:
        return self._resolve(self.cache_dir)

    @property
    def log_path(self) -> Path:
        return self._resolve(self.log_dir)

    def ensure_directories(self) -> None:
        """Create all data directories the app depends on, if missing."""
        for path in (self.upload_path, self.output_path, self.cache_path, self.log_path):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (single source of truth)."""
    return Settings()
