from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import jwt
import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

import deps.db
from config import get_settings
from deps.auth import get_current_user
from deps.db import get_db
from models.user import User
from services.security import create_access_token

settings = get_settings()

OTHER_SECRET = "another-signing-key-that-is-long-enough"


def token(payload: dict[str, Any], *, secret: str | None = None) -> str:
    return jwt.encode(
        payload, secret or settings.secret_key, algorithm=settings.jwt_algorithm
    )


def future() -> datetime:
    return datetime.now(UTC) + timedelta(minutes=5)


class RecordingSession:
    """Stands in for a real session so the dependency can be driven directly."""

    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class TestGetDb:
    def test_yields_a_session(self):
        generator = get_db()

        session = next(generator)

        assert isinstance(session, Session)
        generator.close()

    def test_the_session_is_bound_to_the_configured_database(self):
        generator = get_db()

        session = next(generator)

        assert session.get_bind() is deps.db.engine
        generator.close()

    def test_yields_a_new_session_each_time(self):
        first, second = get_db(), get_db()

        try:
            assert next(first) is not next(second)
        finally:
            first.close()
            second.close()

    def test_closes_the_session_when_the_request_is_done(self, monkeypatch):
        session = RecordingSession()
        monkeypatch.setattr(deps.db, "SessionLocal", lambda: session)

        generator = get_db()
        next(generator)
        assert session.closed is False

        with pytest.raises(StopIteration):
            next(generator)
        assert session.closed is True

    def test_closes_the_session_even_when_the_handler_raises(self, monkeypatch):
        session = RecordingSession()
        monkeypatch.setattr(deps.db, "SessionLocal", lambda: session)

        generator = get_db()
        next(generator)
        with pytest.raises(RuntimeError):
            generator.throw(RuntimeError("handler blew up"))

        assert session.closed is True


class TestGetCurrentUser:
    def test_returns_the_user_the_token_names(self, db: Session, user: User):
        assert get_current_user(db, create_access_token(user.id)) is user

    def test_rejects_a_missing_cookie(self, db: Session):
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(db, None)

        assert exc_info.value.status_code == 401

    def test_rejects_a_malformed_token(self, db: Session):
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(db, "not-a-jwt")

        assert exc_info.value.status_code == 401

    def test_rejects_a_token_signed_with_another_key(self, db: Session, user: User):
        forged = token({"sub": str(user.id), "exp": future()}, secret=OTHER_SECRET)

        with pytest.raises(HTTPException) as exc_info:
            get_current_user(db, forged)

        assert exc_info.value.status_code == 401

    def test_rejects_an_expired_token(self, db: Session, user: User):
        expired = token(
            {"sub": str(user.id), "exp": datetime.now(UTC) - timedelta(minutes=5)}
        )

        with pytest.raises(HTTPException) as exc_info:
            get_current_user(db, expired)

        assert exc_info.value.status_code == 401

    def test_rejects_a_token_with_no_subject(self, db: Session):
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(db, token({"exp": future()}))

        assert exc_info.value.status_code == 401

    def test_rejects_a_subject_that_is_not_a_uuid(self, db: Session):
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(db, token({"sub": "not-a-uuid", "exp": future()}))

        assert exc_info.value.status_code == 401

    def test_rejects_a_valid_token_for_a_user_that_is_gone(self, db: Session):
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(db, create_access_token(uuid4()))

        assert exc_info.value.status_code == 401

    def test_every_failure_gives_the_same_message(self, db: Session, user: User):
        """Nothing in the error tells a caller which part it got wrong."""
        details = set()
        for bad_token in (
            None,
            "not-a-jwt",
            token({"sub": str(user.id), "exp": future()}, secret=OTHER_SECRET),
            create_access_token(uuid4()),
        ):
            with pytest.raises(HTTPException) as exc_info:
                get_current_user(db, bad_token)
            details.add(exc_info.value.detail)

        assert len(details) == 1
