from __future__ import annotations

from datetime import timedelta

from app.auth import (
    authenticate_user,
    create_access_token,
    generate_refresh_token,
    get_token_by_refresh_token,
    store_token,
)
from app.config import settings
from app.dependencies import get_db
from app.models.oauth import TokenResponse

from fastapi import APIRouter, Depends, Form, HTTPException
from sqlalchemy.orm import Session

router = APIRouter(tags=["osu! OAuth 认证"])


@router.post("/oauth/token", response_model=TokenResponse)
async def oauth_token(
    grant_type: str = Form(...),
    client_id: str = Form(...),
    client_secret: str = Form(...),
    scope: str = Form("*"),
    username: str | None = Form(None),
    password: str | None = Form(None),
    refresh_token: str | None = Form(None),
    db: Session = Depends(get_db),
):
    """OAuth 令牌端点"""
    # 验证客户端凭据
    if (
        client_id != settings.OSU_CLIENT_ID
        or client_secret != settings.OSU_CLIENT_SECRET
    ):
        raise HTTPException(status_code=401, detail="Invalid client credentials")

    if grant_type == "password":
        # 密码授权流程
        if not username or not password:
            raise HTTPException(
                status_code=400, detail="Username and password required"
            )

        # 验证用户
        user = authenticate_user(db, username, password)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid username or password")

        # 生成令牌
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(user.id)}, expires_delta=access_token_expires
        )
        refresh_token_str = generate_refresh_token()

        # 存储令牌
        store_token(
            db,
            user.id,
            access_token,
            refresh_token_str,
            settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

        return TokenResponse(
            access_token=access_token,
            token_type="Bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            refresh_token=refresh_token_str,
            scope=scope,
        )

    elif grant_type == "refresh_token":
        # 刷新令牌流程
        if not refresh_token:
            raise HTTPException(status_code=400, detail="Refresh token required")

        # 验证刷新令牌
        token_record = get_token_by_refresh_token(db, refresh_token)
        if not token_record:
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        # 生成新的访问令牌
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(token_record.user_id)}, expires_delta=access_token_expires
        )
        new_refresh_token = generate_refresh_token()

        # 更新令牌
        store_token(
            db,
            token_record.user_id,
            access_token,
            new_refresh_token,
            settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

        return TokenResponse(
            access_token=access_token,
            token_type="Bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            refresh_token=new_refresh_token,
            scope=scope,
        )

    else:
        raise HTTPException(status_code=400, detail="Unsupported grant type")
