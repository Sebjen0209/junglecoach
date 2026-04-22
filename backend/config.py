"""Central configuration loaded from environment variables."""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    riot_api_key: str = Field(default="", alias="RIOT_API_KEY")
    db_path: str = Field(default="./data/junglecoach.db", alias="DB_PATH")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    ai_model: str = Field(default="claude-haiku-4-5-20251001", alias="AI_MODEL")
    current_patch: str = Field(default="16.8", alias="CURRENT_PATCH")
    api_port: int = Field(default=7429, alias="API_PORT")
    # Riot API routing — platform for summoner lookups, region for Match-V5
    riot_platform: str = Field(default="euw1", alias="RIOT_PLATFORM")
    riot_region: str = Field(default="europe", alias="RIOT_REGION")
    # Cloud API — used on startup to check for fresh matchup data.
    # Leave empty to skip the auto-update check (e.g. for offline dev).
    cloud_api_url: str = Field(default="", alias="CLOUD_API_URL")
    # Supabase — used to verify user tokens and enforce post-game limits.
    # Leave empty to skip auth checks (dev mode).
    supabase_url: str = Field(default="", alias="SUPABASE_URL")
    supabase_anon_key: str = Field(default="", alias="SUPABASE_ANON_KEY")

    model_config = {"env_file": ".env", "populate_by_name": True}


settings = Settings()
