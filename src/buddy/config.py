"""Configuration loaded from environment variables (and .env)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # API keys
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")

    # Auth
    auth_token: str = Field(default="dev-insecure-token", alias="BUDDY_AUTH_TOKEN")

    # Storage
    db_path: Path = Field(default=Path("./data/buddy.db"), alias="BUDDY_DB_PATH")
    memory_path: Path = Field(default=Path("./data/memory"), alias="BUDDY_MEMORY_PATH")

    # User / persona
    user_name: str = Field(default="Maverick", alias="BUDDY_USER_NAME")
    persona_name: str = Field(default="Coach", alias="BUDDY_PERSONA_NAME")

    # Behavior
    log_level: str = Field(default="INFO", alias="BUDDY_LOG_LEVEL")
    timezone: str = Field(default="America/Chicago", alias="BUDDY_TIMEZONE")
    consolidation_hour: int = Field(default=3, alias="BUDDY_CONSOLIDATION_HOUR")
    morning_check_in_hour: int = Field(default=7, alias="BUDDY_MORNING_HOUR")
    morning_check_in_minute: int = Field(default=0, alias="BUDDY_MORNING_MINUTE")
    end_of_day_hour: int = Field(default=21, alias="BUDDY_EOD_HOUR")
    end_of_day_minute: int = Field(default=0, alias="BUDDY_EOD_MINUTE")

    # LLM tier pins (optional)
    fast_model_pin: str = Field(default="", alias="BUDDY_FAST_MODEL_PIN")
    reasoning_model_pin: str = Field(default="", alias="BUDDY_REASONING_MODEL_PIN")
    embedding_model: str = Field(default="text-embedding-3-small", alias="BUDDY_EMBEDDING_MODEL")

    # Budget
    budget_soft_usd: float = Field(default=50.0, alias="BUDDY_BUDGET_SOFT_USD")
    budget_hard_usd: float = Field(default=100.0, alias="BUDDY_BUDGET_HARD_USD")

    # Anthropic server-side web search. When enabled the persona can
    # call web_search mid-chat to look up factual information ("what's
    # a typical first-5K training schedule?", "when does Trader Joe's
    # in OKC close?"). Costs per search; we cap at 3/turn in the
    # /converse handler. Disable here if you hit the budget cap or
    # don't want the feature.
    enable_web_search: bool = Field(default=True, alias="BUDDY_ENABLE_WEB_SEARCH")
    web_search_max_uses_per_turn: int = Field(
        default=3, alias="BUDDY_WEB_SEARCH_MAX_USES"
    )

    # Memory git remote
    git_remote: str = Field(default="", alias="BUDDY_GIT_REMOTE")

    # Notifications
    dreams_notification_email: str = Field(
        default="", alias="BUDDY_DREAMS_NOTIFICATION_EMAIL"
    )

    # Phase 5: override system (SMS to a designated approver)
    twilio_account_sid: str = Field(default="", alias="TWILIO_ACCOUNT_SID")
    twilio_auth_token: str = Field(default="", alias="TWILIO_AUTH_TOKEN")
    twilio_from_number: str = Field(default="", alias="TWILIO_FROM_NUMBER")
    override_approver_number: str = Field(
        default="", alias="BUDDY_OVERRIDE_APPROVER_NUMBER"
    )
    override_approver_label: str = Field(
        default="approver", alias="BUDDY_OVERRIDE_APPROVER_LABEL"
    )

    @property
    def sms_configured(self) -> bool:
        return all(
            [
                self.twilio_account_sid,
                self.twilio_auth_token,
                self.twilio_from_number,
                self.override_approver_number,
            ]
        )

    @property
    def db_url(self) -> str:
        return f"sqlite+aiosqlite:///{self.db_path}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reload_settings() -> Settings:
    """Force a re-read; useful in tests."""
    get_settings.cache_clear()
    return get_settings()
