"""Authentication contracts."""

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import DomainModel


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    display_name: str | None = Field(default=None, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserView(DomainModel):
    id: str
    email: str
    display_name: str | None = None
