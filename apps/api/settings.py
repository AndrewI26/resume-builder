from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    frontend_url: str = "http://localhost:5173"
    port: int = 8000

    secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 1 week

    # send auth cookies over HTTPS only; keep off for local http:// development
    cookie_secure: bool = False

    # from the OAuth 2.0 Client ID created in the Google Cloud console
    google_client_id: str | None = None
    google_client_secret: str | None = None
    # must be registered verbatim as an authorized redirect URI on that client
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"

    @property
    def google_oauth_configured(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)


@lru_cache
def get_settings() -> Settings:
    return Settings()
