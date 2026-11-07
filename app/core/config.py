from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    supabase_url: str = Field(
        default="",
        validation_alias=AliasChoices("SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL"),
    )
    supabase_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices(
            "SUPABASE_PUBLISHABLE_KEY",
            "SUPABASE_KEY",
            "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY",
        ),
    )
    environment: str = "development"
    cors_origins: str = ""
    access_token_expire_minutes: int = Field(default=1440, gt=0)
    max_request_body_bytes: int = Field(default=65536, gt=0)
    rate_limit_window_seconds: int = Field(default=60, gt=0)
    auth_rate_limit_requests: int = Field(default=10, gt=0)
    search_rate_limit_requests: int = Field(default=60, gt=0)

    @property
    def supabase_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_key.get_secret_value())

    @property
    def allowed_origins(self) -> list[str]:
        if self.cors_origins.strip():
            return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        if self.environment.lower() == "development":
            return ["http://localhost:3000", "http://127.0.0.1:3000"]
        return []

    def validate_runtime(self) -> None:
        if self.environment.lower() != "production":
            return
        if not self.supabase_configured:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY must be configured in production"
            )
        for origin in self.allowed_origins:
            parsed = urlsplit(origin)
            if (
                origin == "*"
                or parsed.scheme != "https"
                or not parsed.netloc
                or parsed.path
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("Production CORS_ORIGINS must contain exact HTTPS origins")


@lru_cache
def get_settings() -> Settings:
    env_file = ".env" if Path(".env").is_file() else ".env.local"
    return Settings(_env_file=env_file)
