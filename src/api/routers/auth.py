from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from src.api.db import get_session
from src.api.models_db import User
from src.api.schemas import AuthTokenResponse, UserLoginRequest, UserRegisterRequest, UserResponse
from src.api.security import create_access_token, get_current_user, hash_password, verify_password


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthTokenResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: UserRegisterRequest,
    session: Annotated[Session, Depends(get_session)],
):
    email = payload.email.lower().strip()
    existing = session.exec(select(User).where(User.email == email)).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered")

    user = User(email=email, hashed_password=hash_password(payload.password))
    session.add(user)
    session.commit()
    session.refresh(user)

    token = create_access_token(user.id)
    return AuthTokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.post("/login", response_model=AuthTokenResponse)
def login(
    payload: UserLoginRequest,
    session: Annotated[Session, Depends(get_session)],
):
    email = payload.email.lower().strip()
    user = session.exec(select(User).where(User.email == email)).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    token = create_access_token(user.id)
    return AuthTokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.get("/me", response_model=UserResponse)
def me(current_user: Annotated[User, Depends(get_current_user)]):
    return UserResponse.model_validate(current_user)
