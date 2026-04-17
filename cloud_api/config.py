"""Central configuration for the JungleCoach cloud API.

All values are loaded from environment variables — no defaults for secrets.
Railway injects these at runtime; locally they come from .env.
"""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # -------------------------------------------------------------------------
    # Anthropic
    # -------------------------------------------------------------------------
    anthropic_api_key: str = Field(alias="ANTHROPIC_API_KEY")
    # Production uses Sonnet; override to haiku for local cost testing
    ai_model: str = Field(default="claude-sonnet-4-6", alias="AI_MODEL")

    # -------------------------------------------------------------------------
    # Riot Games
    # -------------------------------------------------------------------------
    riot_api_key: str = Field(alias="RIOT_API_KEY")

    # -------------------------------------------------------------------------
    # Supabase (server-side only — service role key never leaves this service)
    # -------------------------------------------------------------------------
    supabase_url: str = Field(alias="SUPABASE_URL")
    supabase_service_role_key: str = Field(alias="SUPABASE_SERVICE_ROLE_KEY")

    # -------------------------------------------------------------------------
    # App
    # -------------------------------------------------------------------------
    environment: str = Field(default="production", alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    # Comma-separated list of allowed CORS origins, e.g.:
    # "https://junglecoach.gg,https://www.junglecoach.gg"
    allowed_origins: str = Field(default="", alias="ALLOWED_ORIGINS")

    model_config = {"env_file": ".env", "populate_by_name": True}

    @field_validator("allowed_origins")
    @classmethod
    def origins_must_not_be_wildcard(cls, v: str) -> str:
        if v.strip() == "*":
            raise ValueError(
                "ALLOWED_ORIGINS must not be '*' in the cloud API — "
                "list explicit origins instead."
            )
        return v

    @property
    def origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


settings = Settings()
