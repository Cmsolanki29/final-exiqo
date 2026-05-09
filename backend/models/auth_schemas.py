"""Pydantic models for authentication API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserSignUp(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def password_bytes(cls, v: str) -> str:
        if len(v.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 bytes (bcrypt limit)")
        return v


class UserSignIn(BaseModel):
    email: EmailStr
    password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., min_length=10)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class AuthUserResponse(BaseModel):
    id: int
    name: str
    email: str
    monthly_income: float
    onboarding_completed: bool
    created_at: datetime


class PasswordReset(BaseModel):
    email: EmailStr


class PasswordUpdate(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)
