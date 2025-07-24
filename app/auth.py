from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import secrets
import string
from typing import Optional

from app.config import settings
from app.database import (
    OAuthToken,
    User as DBUser,
)

import bcrypt
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

# 密码哈希上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# bcrypt 缓存（模拟应用状态缓存）
bcrypt_cache = {}


def verify_password_legacy(plain_password: str, bcrypt_hash: str) -> bool:
    """
    验证密码 - 使用 osu! 的验证方式
    1. 明文密码 -> MD5哈希
    2. MD5哈希 -> bcrypt验证
    """
    # 1. 明文密码转 MD5
    pw_md5 = hashlib.md5(plain_password.encode()).hexdigest().encode()

    # 2. 检查缓存
    if bcrypt_hash in bcrypt_cache:
        return bcrypt_cache[bcrypt_hash] == pw_md5

    # 3. 如果缓存中没有，进行 bcrypt 验证
    try:
        # 验证 MD5 哈希与 bcrypt 哈希
        is_valid = bcrypt.checkpw(pw_md5, bcrypt_hash.encode())

        # 如果验证成功，将结果缓存
        if is_valid:
            bcrypt_cache[bcrypt_hash] = pw_md5

        return is_valid
    except Exception as e:
        print(f"Password verification error: {e}")
        return False


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码（向后兼容）"""
    # 首先尝试新的验证方式
    if verify_password_legacy(plain_password, hashed_password):
        return True

    # 如果失败，尝试标准 bcrypt 验证
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """生成密码哈希 - 使用 osu! 的方式"""
    # 1. 明文密码 -> MD5
    pw_md5 = hashlib.md5(password.encode()).hexdigest().encode()
    # 2. MD5 -> bcrypt
    pw_bcrypt = bcrypt.hashpw(pw_md5, bcrypt.gensalt())
    return pw_bcrypt.decode()


def authenticate_user_legacy(db: Session, name: str, password: str) -> Optional[DBUser]:
    """
    验证用户身份 - 使用类似 from_login 的逻辑
    """
    # 1. 明文密码转 MD5
    pw_md5 = hashlib.md5(password.encode()).hexdigest()

    # 2. 根据用户名查找用户
    user = db.query(DBUser).filter(DBUser.name == name).first()
    if not user:
        return None

    # 3. 验证密码
    if not (user.pw_bcrypt is None and user.pw_bcrypt != ""):
        return None

    # 4. 检查缓存
    if user.pw_bcrypt in bcrypt_cache:
        if bcrypt_cache[user.pw_bcrypt] == pw_md5.encode():
            return user
        else:
            return None

    # 5. 验证 bcrypt
    try:
        is_valid = bcrypt.checkpw(pw_md5.encode(), user.pw_bcrypt.encode())
        if is_valid:
            # 缓存验证结果
            bcrypt_cache[user.pw_bcrypt] = pw_md5.encode()
            return user
    except Exception as e:
        print(f"Authentication error for user {name}: {e}")

    return None


def authenticate_user(db: Session, username: str, password: str) -> Optional[DBUser]:
    """验证用户身份"""
    return authenticate_user_legacy(db, username, password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建访问令牌"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def generate_refresh_token() -> str:
    """生成刷新令牌"""
    length = 64
    characters = string.ascii_letters + string.digits
    return "".join(secrets.choice(characters) for _ in range(length))


def verify_token(token: str) -> Optional[dict]:
    """验证访问令牌"""
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError:
        return None


def store_token(
    db: Session, user_id: int, access_token: str, refresh_token: str, expires_in: int
) -> OAuthToken:
    """存储令牌到数据库"""
    expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

    # 删除用户的旧令牌
    db.query(OAuthToken).filter(OAuthToken.user_id == user_id).delete()

    # 创建新令牌记录
    token_record = OAuthToken(
        user_id=user_id,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
    )
    db.add(token_record)
    db.commit()
    db.refresh(token_record)
    return token_record


def get_token_by_access_token(db: Session, access_token: str) -> Optional[OAuthToken]:
    """根据访问令牌获取令牌记录"""
    return (
        db.query(OAuthToken)
        .filter(
            OAuthToken.access_token == access_token,
            OAuthToken.expires_at > datetime.utcnow(),
        )
        .first()
    )


def get_token_by_refresh_token(db: Session, refresh_token: str) -> Optional[OAuthToken]:
    """根据刷新令牌获取令牌记录"""
    return (
        db.query(OAuthToken)
        .filter(
            OAuthToken.refresh_token == refresh_token,
            OAuthToken.expires_at > datetime.utcnow(),
        )
        .first()
    )
