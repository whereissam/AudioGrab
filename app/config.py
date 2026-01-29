"""Configuration management using Pydantic Settings."""

from pathlib import Path
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Twitter Authentication
    twitter_auth_token: str = ""
    twitter_ct0: str = ""
    twitter_cookie_file: str | None = None

    # Public bearer token used by Twitter web client
    twitter_bearer_token: str = (
        "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCgYR9Wk5bLLMNhyFz4%3D"
        "sIHxcAabN8Z2cIUpYBUSsYGqNFtEGV1VTJFhD4ij8EV2YikPq3"
    )

    # Telegram Bot
    telegram_bot_token: str | None = None

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # Downloads
    download_dir: str = "/tmp/audiograb"
    max_concurrent_downloads: int = 5
    cleanup_after_hours: int = 24

    def get_download_path(self) -> Path:
        """Get download directory as Path, creating if needed."""
        path = Path(self.download_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def has_auth(self) -> bool:
        """Check if authentication credentials are configured."""
        return bool(self.twitter_auth_token and self.twitter_ct0) or bool(
            self.twitter_cookie_file
        )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
