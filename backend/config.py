"""Central configuration loaded from environment variables."""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    riot_api_key: str = Field(default="", alias="RIOT_API_KEY")
    riot_region: str = Field(default="euw1", alias="RIOT_REGION")  # e.g. na1, euw1, kr
    db_path: str = Field(default="./data/junglecoach.db", alias="DB_PATH")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    ai_model: str = Field(default="claude-haiku-4-5-20251001", alias="AI_MODEL")
    current_patch: str = Field(default="15.7", alias="CURRENT_PATCH")
    api_port: int = Field(default=7429, alias="API_PORT")
    # Riot API routing — platform for summoner lookups, region for Match-V5
    riot_platform: str = Field(default="euw1", alias="RIOT_PLATFORM")
    riot_region: str = Field(default="europe", alias="RIOT_REGION")

    model_config = {"env_file": ".env", "populate_by_name": True}


settings = Settings()
