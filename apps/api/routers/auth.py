from fastapi import APIRouter, HTTPException, Response, status

from deps.auth import CurrentUser
from deps.db import Db
from models.user import User
from schemas.user import UserCreate, UserLogin, UserRead
from services.security import (
    ACCESS_TOKEN_COOKIE_NAME,
    hash_password,
    set_access_token_cookie,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, response: Response, db: Db):
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

    set_access_token_cookie(response, user.id)
    return user


@router.post("/login", response_model=UserRead)
def login(payload: UserLogin, response: Response, db: Db):
    user = db.query(User).filter(User.email == payload.email).first()
    if (
        user is None
        or user.hashed_password is None
        or not verify_password(payload.password, user.hashed_password)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    set_access_token_cookie(response, user.id)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response):
    response.delete_cookie(ACCESS_TOKEN_COOKIE_NAME)


@router.get("/me", response_model=UserRead)
def me(current_user: CurrentUser):
    return current_user
