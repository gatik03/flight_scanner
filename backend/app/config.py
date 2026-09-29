"""Validated application configuration."""

from functools import lru_cache
from typing import Annotated

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime configuration, loaded at the application boundary."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = "dev"
    log_level: str = "INFO"
    database_url: str
    redis_url: str
    jwt_secret: SecretStr = Field(min_length=32)
    jwt_alg: str = "HS256"
    access_token_ttl_min: int = Field(default=30, gt=0)
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )
    enabled_providers: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["fake"])
    allow_live_providers: bool = False

    @field_validator("database_url", "redis_url")
    @classmethod
    def require_scheme(cls, value: str) -> str:
        if "://" not in value:
            raise ValueError("URL must include a scheme")
        return value

    @field_validator("cors_origins", "enabled_providers", mode="before")
    @classmethod
    def split_csv_values(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("app_env")
    @classmethod
    def validate_environment(cls, value: str) -> str:
        if value not in {"dev", "test", "prod"}:
            raise ValueError("app_env must be dev, test, or prod")
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process configuration singleton at the composition root."""

    return Settings()  # type: ignore[call-arg]  # Values are loaded from the environment.
