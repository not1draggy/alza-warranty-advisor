"""Authentication endpoints. The rest of the API works anonymously; signing in
adds durable search history."""

import sqlalchemy as sa
from fastapi import APIRouter, status

from app.api.deps import CurrentUserDep, RateLimitDep, SessionDep, SettingsDep
from app.core.errors import Conflict, Unauthorized
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserView

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest, session: SessionDep, settings: SettingsDep, _: RateLimitDep
) -> TokenResponse:
    email = payload.email.lower()
    existing = await session.scalar(sa.select(User).where(User.email == email))
    if existing is not None:
        raise Conflict("An account with that email already exists.")

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
    )
    session.add(user)
    await session.commit()

    return TokenResponse(
        access_token=create_access_token(user.id),
        expires_in=settings.access_token_ttl_minutes * 60,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest, session: SessionDep, settings: SettingsDep, _: RateLimitDep
) -> TokenResponse:
    user = await session.scalar(sa.select(User).where(User.email == payload.email.lower()))
    # Constant-ish work either way so a missing account is not distinguishable by timing.
    if user is None or not verify_password(payload.password, user.password_hash):
        raise Unauthorized("Email or password is incorrect.")
    if not user.is_active:
        raise Unauthorized("This account has been disabled.")

    return TokenResponse(
        access_token=create_access_token(user.id),
        expires_in=settings.access_token_ttl_minutes * 60,
    )


@router.get("/me", response_model=UserView)
async def me(user: CurrentUserDep) -> UserView:
    return UserView.model_validate(user)
