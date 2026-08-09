from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from deps.db import Db
from models.user import User
from security import ACCESS_TOKEN_COOKIE_NAME, decode_access_token

CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
)


def get_current_user(
    db: Session = Db,
    access_token: str | None = Cookie(default=None, alias=ACCESS_TOKEN_COOKIE_NAME),
) -> User:
    if access_token is None:
        raise CREDENTIALS_EXCEPTION

    user_id = decode_access_token(access_token)
    if user_id is None:
        raise CREDENTIALS_EXCEPTION

    user = db.get(User, user_id)
    if user is None:
        raise CREDENTIALS_EXCEPTION

    return user


CurrentUser = Depends(get_current_user)
