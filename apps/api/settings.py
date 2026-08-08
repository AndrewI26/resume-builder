from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    frontend_url: str = "http://localhost:5173"
    port: int = 8000


@lru_cache
def get_settings() -> Settings:
    return Settings()
