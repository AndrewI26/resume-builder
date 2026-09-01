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

    # How many PDF compiles may run at once. The workers are started by the
    # API itself, so this is set when the API starts:
    # ``PDF_WORKER_COUNT=6 bun run dev:api``.
    pdf_worker_count: int = 3

    # The image each compile runs in. Built by ``bun run docker:dev``.
    latex_image: str = "resume-builder-latex"

    frontend_port: str
    backend_port: int

    secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 1 week

    google_client_id: str | None = None
    google_client_secret: str | None = None

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
    def async_database_url(self) -> str:
        """The same database, for psycopg's own async connection.

        ``LISTEN`` needs a connection SQLAlchemy is not driving, and psycopg
        does not understand SQLAlchemy's ``+psycopg`` dialect suffix.
        """
        return self.database_url.replace("postgresql+psycopg://", "postgresql://", 1)

    @property
    def google_oauth_configured(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def cookie_secure(self) -> bool:
        return self.node_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # pyright: ignore[reportCallIssue]
