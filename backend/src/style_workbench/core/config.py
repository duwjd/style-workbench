from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/style_workbench"
    s3_endpoint_url: str = "http://localhost:9000"
    s3_bucket: str = "style-workbench"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"

    anthropic_api_key: str = ""
    openai_api_key: str = ""
    replicate_api_token: str = ""

    log_level: str = "INFO"
    environment: str = "development"


settings = Settings()
