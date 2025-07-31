from __future__ import annotations

from app.auth import get_token_by_access_token
from app.database import User

from .database import get_db

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """获取当前认证用户"""
    token = credentials.credentials

    user = await get_current_user_by_token(token, db)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user


async def get_current_user_by_token(token: str, db: AsyncSession) -> User | None:
    token_record = await get_token_by_access_token(db, token)
    if not token_record:
        return None
    user = (await db.exec(select(User).where(User.id == token_record.user_id))).first()
    return user
