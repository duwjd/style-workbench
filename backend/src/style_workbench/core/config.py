from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/style_workbench"

    anthropic_api_key: str = ""
    openai_api_key: str = ""
    replicate_api_token: str = ""

    log_level: str = "INFO"
    environment: str = "development"

    # ---------------------------------------------------------------------------
    # F02 Prompt Optimizer (spec §4 FR-8)
    # ---------------------------------------------------------------------------
    # Set to False to disable LlmPromptModifier and fall back to NoopPromptModifier.
    # This preserves F01 golden test regression (AC-9).
    prompt_optimizer_enabled: bool = True

    # Default model for the Prompt Optimizer (spec §4 FR-2).
    # Override via PROMPT_OPTIMIZER_MODEL environment variable.
    prompt_optimizer_model: str = "claude-opus-4-7"


settings = Settings()
