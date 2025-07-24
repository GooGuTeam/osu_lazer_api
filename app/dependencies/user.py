from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth import get_token_by_access_token

from .database import get_db
from app.database import (
    User as DBUser,
)

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> DBUser:
    """获取当前认证用户"""
    token = credentials.credentials

    user = await get_current_user_by_token(token, db)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user


async def get_current_user_by_token(token: str, db: Session) -> DBUser | None:
    token_record = get_token_by_access_token(db, token)
    if not token_record:
        return None
    user = db.query(DBUser).filter(DBUser.id == token_record.user_id).first()
    return user
