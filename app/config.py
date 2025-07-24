from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    # 数据库设置
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "mysql+pymysql://root:password@localhost:3306/osu_api"
    )
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # JWT 设置
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440")
    )

    # OAuth 设置
    OSU_CLIENT_ID: str = os.getenv("OSU_CLIENT_ID", "5")
    OSU_CLIENT_SECRET: str = os.getenv(
        "OSU_CLIENT_SECRET", "FGc9GAtyHzeQDshWP5Ah7dega8hJACAJpQtw6OXk"
    )

    # 服务器设置
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"

    # SignalR 设置
    SIGNALR_NEGOTIATE_TIMEOUT: int = int(os.getenv("SIGNALR_NEGOTIATE_TIMEOUT", "30"))
    SIGNALR_PING_INTERVAL: int = int(os.getenv("SIGNALR_PING_INTERVAL", "120"))


settings = Settings()
