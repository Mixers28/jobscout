"""Application settings loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="JOBSCOUT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "dev"
    database_url: str = "sqlite+pysqlite:///./jobscout.db"
    redis_url: str = "redis://localhost:6379/0"
    worker_queue_key: str = "jobscout:jobs"
    skills_profile_path: str = "skills_profile.json"
    truth_bank_path: str = "truth_bank.yml"
    scoring_weights_path: str = "scoring_weights.yml"
    rubric_path: str = "RUBRIC.md"
    prompt_guardrail_path: str = "prompt_guardrail.md"
    scheduler_interval_seconds: int = 86400
    scheduler_max_retries: int = 2
    scheduler_backoff_seconds: int = 2
    notification_score_threshold: float = 80.0
    notification_top_n: int = 5
    notification_lookback_hours: int = 24
    discord_webhook_url: str = ""
    smtp_host: str = ""
    smtp_port: int = 25
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = False
    notification_email_from: str = ""
    notification_email_to: str = ""
    imap_host: str = ""
    imap_port: int = 993
    imap_username: str = ""
    imap_password: str = ""
    imap_use_ssl: bool = True
    imap_mailbox: str = "INBOX"
    imap_max_fetch: int = 50


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
