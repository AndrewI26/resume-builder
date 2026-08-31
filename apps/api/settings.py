from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    node_env: Literal["development", "production"]

    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_port: int

    frontend_port: str
    backend_port: int

    secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 1 week

    # send auth cookies over HTTPS only; keep off for local http:// development
    cookie_secure: bool = False

    google_client_id: str | None = None
    google_client_secret: str | None = None

    # the LaTeX compile service. The token is shared with it and gates every
    # request; without one, PDF export is off rather than attempted.
    compiler_port: int = 8100
    compiler_token: str | None = None

    @property
    def frontend_url(self) -> str:
        return f"http://localhost:{self.frontend_port}"

    @property
    def google_redirect_uri(self) -> str:
        return f"http://localhost:{self.backend_port}/auth/google/callback"

    @property
    def database_url(self) -> str:
        return f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}@localhost:{self.postgres_port}/{self.postgres_db}"

    @property
    def compiler_url(self) -> str:
        """Where the compile service listens.

        It runs in docker-compose while the API runs on the host, so this is a
        published localhost port rather than a compose service name.
        """
        return f"http://localhost:{self.compiler_port}"

    @property
    def google_oauth_configured(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # pyright: ignore[reportCallIssue]
