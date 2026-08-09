from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy.orm import Session

from deps.auth import CurrentUser
from deps.db import Db
from models.user import User
from schemas.user import UserCreate, UserLogin, UserRead
from security import (
    ACCESS_TOKEN_COOKIE_NAME,
    create_access_token,
    hash_password,
    verify_password,
)
from settings import get_settings

router = APIRouter(prefix="/auth", tags=["Auth"])

settings = get_settings()


def _set_access_token_cookie(response: Response, user_id: UUID) -> None:
    token = create_access_token(user_id)
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
    )


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, response: Response, db: Session = Db):
    existing_user = db.query(User).filter(User.email == payload.email).first()
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    user = User(email=payload.email, hashed_password=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)

    _set_access_token_cookie(response, user.id)
    return user


@router.post("/login", response_model=UserRead)
def login(payload: UserLogin, response: Response, db: Session = Db):
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    _set_access_token_cookie(response, user.id)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response):
    response.delete_cookie(ACCESS_TOKEN_COOKIE_NAME)


@router.get("/me", response_model=UserRead)
def me(current_user: User = CurrentUser):
    return current_user
