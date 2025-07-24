# OAuth 相关模型
from __future__ import annotations

from pydantic import BaseModel


class TokenRequest(BaseModel):
    grant_type: str
    username: str | None = None
    password: str | None = None
    refresh_token: str | None = None
    client_id: str
    client_secret: str
    scope: str = "*"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    refresh_token: str
    scope: str = "*"


class UserCreate(BaseModel):
    username: str
    password: str
    email: str
    country_code: str = "CN"
