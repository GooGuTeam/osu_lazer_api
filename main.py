from __future__ import annotations

from datetime import datetime

from app.config import settings
from app.router import api_router, auth_router, signalr_router

from fastapi import FastAPI

# 注意: 表结构现在通过 migrations 管理，不再自动创建
# 如需创建表，请运行: python quick_sync.py

app = FastAPI(title="osu! API 模拟服务器", version="1.0.0")
app.include_router(api_router, prefix="/api/v2")
app.include_router(signalr_router, prefix="/signalr")
app.include_router(auth_router)


@app.get("/")
async def root():
    """根端点"""
    return {"message": "osu! API 模拟服务器正在运行"}


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


# @app.get("/api/v2/friends")
# async def get_friends():
#     return JSONResponse(
#         content=[
#             {
#                 "id": 123456,
#                 "username": "BestFriend",
#                 "is_online": True,
#                 "is_supporter": False,
#                 "country": {"code": "US", "name": "United States"},
#             }
#         ]
#     )


# @app.get("/api/v2/notifications")
# async def get_notifications():
#     return JSONResponse(content={"notifications": [], "unread_count": 0})


# @app.post("/api/v2/chat/ack")
# async def chat_ack():
#     return JSONResponse(content={"status": "ok"})


# @app.get("/api/v2/users/{user_id}/{mode}")
# async def get_user_mode(user_id: int, mode: str):
#     return JSONResponse(
#         content={
#             "id": user_id,
#             "username": "测试测试测",
#             "statistics": {
#                 "level": {"current": 97, "progress": 96},
#                 "pp": 114514,
#                 "global_rank": 666,
#                 "country_rank": 1,
#                 "hit_accuracy": 100,
#             },
#             "country": {"code": "JP", "name": "Japan"},
#         }
#     )


# @app.get("/api/v2/me")
# async def get_me():
#     return JSONResponse(
#         content={
#             "id": 15651670,
#             "username": "Googujiang",
#             "is_online": True,
#             "country": {"code": "JP", "name": "Japan"},
#             "statistics": {
#                 "level": {"current": 97, "progress": 96},
#                 "pp": 2826.26,
#                 "global_rank": 298026,
#                 "country_rank": 11220,
#                 "hit_accuracy": 95.7168,
#             },
#         }
#     )


# @app.post("/signalr/metadata/negotiate")
# async def metadata_negotiate(negotiateVersion: int = 1):
#     return JSONResponse(
#         content={
#             "connectionId": "abc123",
#             "availableTransports": [
#                 {"transport": "WebSockets", "transferFormats": ["Text", "Binary"]}
#             ],
#         }
#     )


# @app.post("/signalr/spectator/negotiate")
# async def spectator_negotiate(negotiateVersion: int = 1):
#     return JSONResponse(
#         content={
#             "connectionId": "spec456",
#             "availableTransports": [
#                 {"transport": "WebSockets", "transferFormats": ["Text", "Binary"]}
#             ],
#         }
#     )


# @app.post("/signalr/multiplayer/negotiate")
# async def multiplayer_negotiate(negotiateVersion: int = 1):
#     return JSONResponse(
#         content={
#             "connectionId": "multi789",
#             "availableTransports": [
#                 {"transport": "WebSockets", "transferFormats": ["Text", "Binary"]}
#             ],
#         }
#     )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG
    )
