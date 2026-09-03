"""The token that keeps the local API to the app that started it.

Worth testing directly rather than through the desktop app, because the failure
this prevents is silent: without it every endpoint still works, and the only
difference is that anything else running on the machine can read the library
too.
"""

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from services.sidecar_guard import TOKEN_HEADER, sidecar_token_guard

TOKEN = "a-secret-the-shell-generated"


@pytest.fixture
def client() -> TestClient:
    """A minimal app wired the way main.py wires the real one."""
    app = FastAPI()

    @app.get("/thing")
    def thing() -> dict[str, str]:
        return {"ok": "yes"}

    # guard first, so CORS ends up outside it — the same ordering main.py
    # relies on for preflights to be answered rather than turned away
    app.middleware("http")(sidecar_token_guard(TOKEN))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return TestClient(app)


def test_the_right_token_gets_through(client: TestClient) -> None:
    response = client.get("/thing", headers={TOKEN_HEADER: TOKEN})

    assert response.status_code == 200


def test_no_token_is_refused(client: TestClient) -> None:
    """What another program on the machine would send."""
    response = client.get("/thing")

    assert response.status_code == 401


def test_a_wrong_token_is_refused(client: TestClient) -> None:
    response = client.get("/thing", headers={TOKEN_HEADER: "guessed"})

    assert response.status_code == 401


def test_a_token_that_merely_starts_right_is_refused(client: TestClient) -> None:
    """A prefix match would make the secret guessable a byte at a time."""
    response = client.get("/thing", headers={TOKEN_HEADER: TOKEN[:-1]})

    assert response.status_code == 401


def test_a_preflight_is_answered_without_one(client: TestClient) -> None:
    """A preflight cannot carry the header — it is asking to be allowed to send it.

    Refusing it would mean the browser never issues the real request, and the
    app would fail with a CORS error that says nothing about tokens.
    """
    response = client.options(
        "/thing",
        headers={
            "Origin": "app://bundle",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": TOKEN_HEADER,
        },
    )

    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers
