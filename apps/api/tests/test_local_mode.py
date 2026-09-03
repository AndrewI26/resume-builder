"""The API as the desktop app runs it.

Local mode is a second deployment of the same application, and almost all of
it is the same code — which is the point, and also why it needs testing of its
own: the parts that differ are few enough to be easy to break without any of
the 600-odd tests above noticing.

Settings are read once and cached, and modules bind them at import, so these
tests move the mode on the already-imported settings objects rather than
rebuilding them. That is what a running process would look like anyway: one
mode, decided before the first request.
"""

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

import deps.auth
import main
import services.compiler
from config import CLOUD_REQUIRED, Settings
from db import prepare_sqlite
from deps.auth import LOCAL_USER_EMAIL, get_local_user
from models.user import User


@pytest.fixture
def local_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Put the modules that branch on it into local mode."""
    for module in (deps.auth, main, services.compiler):
        monkeypatch.setattr(module.settings, "mode", "local")


class TestTheLocalUser:
    def test_there_is_one_without_signing_in(
        self, client: TestClient, local_mode: None
    ) -> None:
        """The whole premise: open the app and start, with no account.

        In cloud mode this same request with no cookie is a 401.
        """
        response = client.get("/auth/me")

        assert response.status_code == 200
        assert response.json()["email"] == LOCAL_USER_EMAIL

    def test_it_is_the_same_user_every_time(
        self, client: TestClient, local_mode: None
    ) -> None:
        """Otherwise every request would file its work under a new owner."""
        first = client.get("/auth/me").json()["id"]
        second = client.get("/auth/me").json()["id"]

        assert first == second

    def test_their_work_is_theirs_on_the_next_request(
        self, client: TestClient, local_mode: None
    ) -> None:
        """Ownership still decides what a request can see; it is just implicit."""
        created = client.post(
            "/experience/",
            json={
                "company": "Acme",
                "position": "Engineer",
                "duration": "2020 - 2022",
                "location": "New York, NY",
                "bullet_points": [],
            },
        )
        assert created.status_code == 201

        listed = client.get("/experience/")
        assert [row["id"] for row in listed.json()] == [created.json()["id"]]

    def test_a_cookie_is_ignored_rather_than_rejected(
        self, client: TestClient, local_mode: None
    ) -> None:
        """A stale token from a previous cloud session must not lock anyone out."""
        client.cookies.set("access_token", "not-a-real-token")

        response = client.get("/auth/me")

        assert response.status_code == 200
        assert response.json()["email"] == LOCAL_USER_EMAIL

    def test_signing_in_is_still_refused_without_credentials(
        self, client: TestClient
    ) -> None:
        """The contrast: cloud mode is unchanged by any of this."""
        assert client.get("/auth/me").status_code == 401


class TestGetLocalUser:
    def test_it_creates_the_user_once(self, db: Session) -> None:
        first = get_local_user(db)
        second = get_local_user(db)

        assert first.id == second.id
        assert db.query(User).filter(User.email == LOCAL_USER_EMAIL).count() == 1


class TestSettings:
    def test_a_local_install_needs_no_configuration(self) -> None:
        """It ships without a .env, and nobody is going to write one."""
        settings = Settings(mode="local", _env_file=None)

        assert settings.is_local
        assert settings.database_url.startswith("sqlite+pysqlite:///")
        # nothing local signs a token, but the security module wants a key
        assert settings.secret_key

    def test_a_hosted_install_still_refuses_to_start_half_configured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The defaults are for the desktop; the server must not inherit them.

        Giving a column a default is how local mode gets to omit it, and it
        would be an easy way to turn a missing POSTGRES_PASSWORD in production
        from a refusal to boot into a connection failure much later.
        """
        for name in CLOUD_REQUIRED:
            monkeypatch.delenv(name.upper(), raising=False)

        with pytest.raises(ValueError, match="cloud mode needs"):
            Settings(mode="cloud", _env_file=None)

    def test_the_database_sits_in_the_directory_it_is_given(self) -> None:
        settings = Settings(
            mode="local",
            local_data_dir=Path("/tmp/somewhere"),
            _env_file=None,
        )

        assert settings.database_path == Path("/tmp/somewhere/resume-builder.sqlite")


class TestBootstrap:
    def test_a_fresh_database_gets_the_schema_and_is_at_head(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """First launch after an install: there is no file, and no time to migrate."""
        import services.local_bootstrap as bootstrap

        settings = Settings(mode="local", local_data_dir=tmp_path, _env_file=None)
        monkeypatch.setattr(bootstrap, "settings", settings)

        engine = prepare_sqlite(create_engine(settings.database_url))
        bootstrap.bootstrap_local_database(engine)

        tables = set(inspect(engine).get_table_names())
        assert {"users", "resumes", "expirences", "alembic_version"} <= tables

        # stamped rather than migrated: the revisions were written for Postgres
        # and would not replay here, and there was nothing to carry forward
        with engine.connect() as connection:
            version = connection.exec_driver_sql(
                "SELECT version_num FROM alembic_version"
            ).scalar()
        assert version is not None

        engine.dispose()

    def test_opening_it_again_leaves_the_data_alone(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Every launch after the first runs this too."""
        import services.local_bootstrap as bootstrap

        settings = Settings(mode="local", local_data_dir=tmp_path, _env_file=None)
        monkeypatch.setattr(bootstrap, "settings", settings)

        engine = prepare_sqlite(create_engine(settings.database_url))
        bootstrap.bootstrap_local_database(engine)

        with Session(engine) as session:
            user = get_local_user(session)
            user_id = user.id

        bootstrap.bootstrap_local_database(engine)

        with Session(engine) as session:
            assert session.get(User, user_id) is not None

        engine.dispose()

    def test_it_makes_the_directory_it_was_pointed_at(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The shell names a per-user directory that may not exist yet."""
        import services.local_bootstrap as bootstrap

        target = tmp_path / "not" / "yet" / "there"
        settings = Settings(mode="local", local_data_dir=target, _env_file=None)
        monkeypatch.setattr(bootstrap, "settings", settings)

        engine = prepare_sqlite(create_engine(settings.database_url))
        bootstrap.bootstrap_local_database(engine)

        assert target.is_dir()
        engine.dispose()


class TestFindingTheEngine:
    """A desktop install ships its own TeX; a server has one installed."""

    def test_the_bundled_distribution_is_looked_at_first(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            services.compiler.settings, "texlive_bin", Path("/bundle/texlive/bin")
        )

        assert services.compiler._lookup_path().startswith(
            f"/bundle/texlive/bin{os.pathsep}"
        )

    def test_without_one_nothing_changes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(services.compiler.settings, "texlive_bin", None)

        assert services.compiler._lookup_path() == os.environ.get("PATH", os.defpath)

    def test_the_engine_still_inherits_a_small_environment(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Bundling TeX must not undo the fencing around the child process."""
        monkeypatch.setattr(
            services.compiler.settings, "texlive_bin", Path("/bundle/texlive/bin")
        )

        environment = services.compiler._environment(Path("/tmp/compile-x"))

        assert environment["PATH"] == f"/bundle/texlive/bin{os.pathsep}{os.defpath}"
        assert environment["openin_any"] == "p"
        assert environment["openout_any"] == "p"
        assert "SECRET_KEY" not in environment
