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

    # Public bearer token used by Twitter web client (not a secret)
    # This is the same token used by twitter.com - can be overridden via TWITTER_BEARER_TOKEN env var
    twitter_bearer_token: str = (
        "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCgYR9Wk5bLLMNhyFz4%3D"
        "sIHxcAabN8Z2cIUpYBUSsYGqNFtEGV1VTJFhD4ij8EV2YikPq3"
    )

    # Telegram Bot
    telegram_bot_token: str | None = None

    # Server
    host: str = "127.0.0.1"  # Bind to localhost by default for security
    port: int = 8000
    debug: bool = False

    # API Authentication (optional - if set, requires X-API-Key header)
    api_key: str | None = None

    # CORS (comma-separated origins, or "*" for all)
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # Rate limiting (requests per minute)
    rate_limit: str = "60/minute"  # Default: 60 requests per minute
    rate_limit_enabled: bool = True

    # Request timeout (seconds)
    request_timeout: int = 300  # 5 minutes default for long downloads

    # Sentry error tracking (optional)
    sentry_dsn: str | None = None
    sentry_environment: str = "development"
    sentry_traces_sample_rate: float = 0.1  # 10% of transactions

    # Downloads
    download_dir: str = "./output"
    max_concurrent_downloads: int = 5
    cleanup_after_hours: int = 24

    # Speaker Diarization (pyannote)
    huggingface_token: str | None = None

    # LLM Summarization
    llm_provider: str = "ollama"  # ollama, openai, anthropic, openai_compatible
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str | None = None  # For OpenAI-compatible endpoints
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-3-haiku-20240307"

    # Subscription Worker
    subscription_worker_enabled: bool = True
    subscription_check_interval: int = 3600  # Check every hour (in seconds)
    subscription_max_concurrent: int = 2  # Max concurrent downloads per check
    subscription_webhook_url: str | None = None  # Optional webhook for notifications

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
