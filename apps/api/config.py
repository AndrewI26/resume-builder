import secrets
from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

# What a hosted deployment cannot start without. These have defaults so that a
# desktop install — which has no Postgres, no queue and no .env to read — can
# leave them out, but a cloud one leaving them out is a misconfiguration worth
# refusing to boot over rather than discovering at the first query.
CLOUD_REQUIRED = (
    "node_env",
    "postgres_user",
    "postgres_password",
    "postgres_db",
    "postgres_port",
    "frontend_port",
    "backend_port",
    "secret_key",
)


class Settings(BaseSettings):
    """How this instance is deployed, and everything that follows from it.

    The same application runs two ways. ``cloud`` is the hosted API: Postgres,
    a queue, accounts, several people. ``local`` is the copy inside the desktop
    app, which has one person, no network and no server — a SQLite file next to
    their documents. Every setting below that a local install cannot supply has
    a default for that reason: the desktop app ships without a .env, and asking
    someone to write one before their resume tool opens is not an option.
    """

    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    node_env: Literal["development", "production"] = "production"
    mode: Literal["cloud", "local"] = "cloud"

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
    # inside one would mean handing it a Docker socket. A desktop install is
    # forced to "local" below — nobody installs Docker to write a resume.
    latex_backend: Literal["docker", "local"] = "docker"

    # The image a "docker" compile runs in. Built by ``bun run docker:latex``.
    latex_image: str = "resume-builder-latex"

    frontend_port: str = "5173"
    backend_port: int = 8000

    secret_key: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 1 week

    google_client_id: str | None = None
    google_client_secret: str | None = None

    # Where the desktop app keeps its database. The shell passes its own
    # per-user application data directory; the default is only for running
    # local mode by hand.
    local_data_dir: Path = Path.home() / ".resume-builder"

    # The bundled TeX distribution's bin directory. A local install cannot
    # count on pdfTeX being on PATH — most people have never installed one —
    # so the desktop app ships its own and says where it is.
    texlive_bin: Path | None = None

    # A secret the desktop shell generates per run and requires on every
    # request. The sidecar listens on loopback, which is private to the machine
    # but not to the person using it: any other program running as them could
    # otherwise read the whole library by asking. See ``require_sidecar_token``.
    sidecar_token: str | None = None

    @model_validator(mode="after")
    def _check_mode_requirements(self) -> Self:
        if self.mode == "cloud":
            missing = [
                name for name in CLOUD_REQUIRED if name not in self.model_fields_set
            ]
            if missing:
                raise ValueError(
                    "cloud mode needs " + ", ".join(sorted(missing)).upper()
                )
            return self

        # A desktop install compiles in its own process. Nobody installs Docker
        # to write a resume, and the container is not the boundary it is on a
        # server: the whole application is already running on one person's
        # machine, under their own account.
        self.latex_backend = "local"

        if not self.secret_key:
            # Nothing local signs a token — there is no account to sign in to,
            # and get_current_user never reads a cookie — but the security
            # module wants a key at import. A per-process one is the honest
            # value: anything it signed would be meaningless outside this run.
            self.secret_key = secrets.token_hex(32)

        return self

    @property
    def is_local(self) -> bool:
        return self.mode == "local"

    @property
    def frontend_url(self) -> str:
        return f"http://localhost:{self.frontend_port}"

    @property
    def google_redirect_uri(self) -> str:
        return f"http://localhost:{self.backend_port}/auth/google/callback"

    @property
    def database_path(self) -> Path:
        return self.local_data_dir / "resume-builder.sqlite"

    @property
    def database_url(self) -> str:
        if self.is_local:
            return f"sqlite+pysqlite:///{self.database_path}"

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
