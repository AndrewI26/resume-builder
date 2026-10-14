from functools import lru_cache
from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

# What the API cannot start without. Leaving one out is a misconfiguration
# worth refusing to boot over rather than discovering at the first query.
REQUIRED = (
    "node_env",
    "postgres_user",
    "postgres_password",
    "postgres_db",
    "postgres_port",
    "backend_port",
    "secret_key",
)


class Settings(BaseSettings):
    """How this instance is deployed, and everything that follows from it."""

    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    node_env: Literal["development", "production"] = "production"

    # ``localhost`` is right when the app runs on the host against the compose
    # database; the containers override this with the service name.
    postgres_host: str = "localhost"

    postgres_user: str = ""
    postgres_password: str = ""
    postgres_db: str = ""
    postgres_port: int = 5432

    # How many PDF compiles may run at once. The workers are started by the
    # API itself, so this is set when the API starts:
    # ``PDF_WORKER_COUNT=6 bun run dev:api``.
    pdf_worker_count: int = 3

    # How the engine is fenced. "docker" gives each compile a container of its
    # own and is right when the API runs on the host; the worker container sets
    # "local", because it is already the boundary and starting containers from
    # inside one would mean handing it a Docker socket.
    latex_backend: Literal["docker", "local"] = "docker"

    # The image a "docker" compile runs in. Built by ``bun run docker:latex``.
    latex_image: str = "resume-builder-latex"

    # Where people open the app: CORS lets it call the API, and sign in with
    # Google lands back on it. The default is the vite dev server.
    public_url: str = "http://localhost:5173"
    backend_port: int = 8000

    secret_key: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 1 week

    google_client_id: str | None = None
    google_client_secret: str | None = None

    # Where a browser reaches the API, when that is not the backend port on
    # localhost: behind docker-compose.yml's reverse proxy it is PUBLIC_URL's
    # /api, and Google has to be sent back there.
    public_api_url: str | None = None

    @model_validator(mode="after")
    def _check_required(self) -> Self:
        missing = [name for name in REQUIRED if name not in self.model_fields_set]
        if missing:
            raise ValueError("the API needs " + ", ".join(sorted(missing)).upper())
        return self

    @property
    def frontend_url(self) -> str:
        return self.public_url.rstrip("/")

    @property
    def google_redirect_uri(self) -> str:
        base = self.public_api_url or f"http://localhost:{self.backend_port}"
        return f"{base.rstrip('/')}/auth/google/callback"

    @property
    def api_path_prefix(self) -> str:
        """The path the browser sees in front of the API's own routes.

        Empty when the API is reached directly; ``/api`` behind the reverse
        proxy, which strips it before the request arrives. Anything scoped to
        a path in the browser, like a cookie, has to include it.
        """
        if self.public_api_url is None:
            return ""
        return urlsplit(self.public_api_url).path.rstrip("/")

    @property
    def database_url(self) -> str:
        return f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

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
    return Settings()
