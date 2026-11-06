from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    supabase_url: str = ""
    supabase_key: str = ""
    google_maps_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    groq_api_key: str = ""
    secret_key: str = "dev-only-change-me"
    environment: str = "development"
    access_token_expire_minutes: int = 1440
    algorithm: str = "HS256"

    @property
    def supabase_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_key)

    @property
    def maps_configured(self) -> bool:
        return bool(self.google_maps_api_key)

    @property
    def llm_provider(self) -> str | None:
        if self.openai_api_key:
            return "openai"
        if self.groq_api_key:
            return "groq"
        if self.anthropic_api_key:
            return "anthropic"
        return None


@lru_cache
def get_settings() -> Settings:
    return Settings()
