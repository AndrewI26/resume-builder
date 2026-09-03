from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from config import get_settings
from deps.db import Db
from models.user import User
from services.security import ACCESS_TOKEN_COOKIE_NAME, decode_access_token

settings = get_settings()

CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
)

# The owner of everything in a local database. The desktop app has no sign-in
# and no second person to keep anything separate from, but the schema is the
# hosted one, where every row belongs to a user — so local mode has a user. It
# is also what makes signing in later a transfer of ownership rather than a
# migration: these rows already have the right shape, they just change hands.
# ``example.com`` because RFC 2606 reserves it for exactly this: an address
# that is well-formed, so the schemas validating one still accept it, and can
# never belong to anybody. Nothing is ever sent to it. The desktop UI has no
# reason to show it either — there is nobody signed in to show.
LOCAL_USER_EMAIL = "local@example.com"


def get_local_user(db: Session) -> User:
    """The local user, created on first use."""
    user = db.scalar(select(User).where(User.email == LOCAL_USER_EMAIL))
    if user is not None:
        return user

    user = User(email=LOCAL_USER_EMAIL)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_current_user(
    db: Db,
    access_token: str | None = Cookie(default=None, alias=ACCESS_TOKEN_COOKIE_NAME),
) -> User:
    """Who is asking.

    In local mode nobody is signed in and nobody can be: the database is a file
    on one person's computer, reachable only from that computer, and demanding
    a token to read it would protect them from themselves. This is the only
    place that distinction lives — everything downstream keeps checking
    ownership exactly as it does for the hosted app.
    """
    if settings.is_local:
        return get_local_user(db)

    if access_token is None:
        raise CREDENTIALS_EXCEPTION

    user_id = decode_access_token(access_token)
    if user_id is None:
        raise CREDENTIALS_EXCEPTION

    user = db.get(User, user_id)
    if user is None:
        raise CREDENTIALS_EXCEPTION

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
