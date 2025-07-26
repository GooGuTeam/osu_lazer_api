from __future__ import annotations

import json
import time
from typing import Literal, Optional
import uuid

from app.database import User as DBUser
from app.dependencies import get_current_user
from app.dependencies.database import get_db
from app.dependencies.user import get_current_user_by_token
from app.models.signalr import NegotiateResponse, Transport
from app.router.signalr.packet import SEP

from .hub import Hubs

from fastapi import APIRouter, Depends, Header, Query, Request, WebSocket, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.websockets import WebSocketDisconnect

security = HTTPBearer(auto_error=False)  # 设置auto_error=False允许可选认证

router = APIRouter()


async def get_authenticated_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    access_token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db)
) -> DBUser:
    """获取认证用户，支持多种认证方式"""
    token = None

    # 调试日志：输出所有headers和查询参数
    print(f"DEBUG: Request method: {request.method}")
    print(f"DEBUG: Request headers: {dict(request.headers)}")
    print(f"DEBUG: Request query params: {dict(request.query_params)}")
    print(f"DEBUG: credentials: {credentials}")
    print(f"DEBUG: access_token query: {access_token}")
    print(f"DEBUG: authorization header: {authorization}")

    # 1. 尝试从Authorization header获取token
    if credentials:
        token = credentials.credentials
        print(f"DEBUG: Got token from credentials: {token[:10]}...")
    # 2. 尝试从query参数获取token
    elif access_token:
        token = access_token
        print(f"DEBUG: Got token from query: {token[:10]}...")
    # 3. 尝试从直接的Authorization header获取token
    elif authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        print(f"DEBUG: Got token from auth header: {token[:10]}...")
    # 4. 尝试从WebSocket特有的header获取token（用于WebSocket连接）
    elif hasattr(request, 'headers'):
        for name, value in request.headers.items():
            if name.lower() == "authorization" and value.startswith("Bearer "):
                token = value[7:]
                print(f"DEBUG: Got token from headers iteration: {token[:10]}...")
                break

    if not token:
        print("DEBUG: No token found in any source")
        raise HTTPException(status_code=403, detail="Authorization required")

    user = await get_current_user_by_token(token, db)
    if not user:
        print(f"DEBUG: Token validation failed for token: {token[:10]}...")
        raise HTTPException(status_code=403, detail="Invalid or expired token")

    print(f"DEBUG: Successfully authenticated user {user.id}")
    return user


@router.post("/{hub}/negotiate", response_model=NegotiateResponse)
@router.get("/{hub}/negotiate", response_model=NegotiateResponse)
async def negotiate(
    hub: Literal["spectator", "multiplayer", "metadata"],
    request: Request,
    negotiate_version: int = Query(1, alias="negotiateVersion"),
):
    """
    SignalR negotiate endpoint - 不需要认证，只是返回连接信息
    实际的认证在WebSocket连接时进行
    """
    # 生成一个临时的连接ID，实际的用户ID在WebSocket连接时确定
    connectionId = str(uuid.uuid4())
    connectionToken = f"temp:{connectionId}"

    # 不需要添加到waited_clients，因为没有用户ID
    # 认证将在WebSocket连接时进行

    return NegotiateResponse(
        connectionId=connectionId,
        connectionToken=connectionToken,
        negotiateVersion=negotiate_version,
        availableTransports=[Transport(
            transport="WebSockets",
            transferFormats=["Binary", "Text"]  # 支持Both Binary and Text格式
        )],
        # 不设置url字段，让客户端使用原始端点的WebSocket版本
    )


@router.websocket("/notifications")
async def notifications_websocket(
    websocket: WebSocket,
    db: AsyncSession = Depends(get_db),
):
    """处理通知WebSocket连接，这是一个直接的WebSocket连接，不是SignalR hub"""
    try:
        # 先接受连接，然后进行认证
        await websocket.accept()

        # 发送认证质询或等待认证消息
        # osu!客户端会在连接后发送认证信息
        print("DEBUG: Notifications WebSocket connection accepted, waiting for auth...")

        # 保持连接活跃，处理通知
        while True:
            try:
                # 等待客户端消息
                data = await websocket.receive_text()
                print(f"DEBUG: Received notifications message: {data}")

                # 如果收到ping，回复pong
                if data == "ping":
                    await websocket.send_text("pong")
                else:
                    # 解析其他消息（如果需要）
                    try:
                        message = json.loads(data)
                        # 处理客户端消息
                        print(f"DEBUG: Parsed notifications message: {message}")
                    except json.JSONDecodeError:
                        # 忽略无效的JSON消息
                        print(f"DEBUG: Invalid JSON in notifications: {data}")
                        pass

            except WebSocketDisconnect:
                print("DEBUG: Notifications WebSocket disconnected")
                break
            except Exception as e:
                print(f"Error in notifications websocket: {e}")
                break

    except Exception as e:
        print(f"Error setting up notifications websocket: {e}")
        try:
            await websocket.close(code=1008)
        except:
            pass


@router.websocket("/{hub}")
async def connect(
    hub: Literal["spectator", "multiplayer", "metadata"],
    websocket: WebSocket,
    id: str,
    db: AsyncSession = Depends(get_db),
):
    # 从WebSocket headers中提取Authorization token
    authorization_header = None
    for name, value in websocket.headers.items():
        if name.lower() == "authorization":
            authorization_header = value
            break

    if not authorization_header:
        await websocket.close(code=1008)
        return

    # 提取Bearer token
    if not authorization_header.startswith("Bearer "):
        await websocket.close(code=1008)
        return

    token = authorization_header[7:]  # 移除 "Bearer " 前缀
    user = await get_current_user_by_token(token, db)
    if not user:
        await websocket.close(code=1008)
        return

    # 如果ID是临时的(以temp:开头)，用实际用户ID替换
    if id.startswith("temp:"):
        user_id = str(user.id)
        connection_token = f"{user_id}:{uuid.uuid4()}"
    else:
        # 检查ID格式是否正确
        try:
            user_id = id.split(":")[0]
            if str(user.id) != user_id:
                await websocket.close(code=1008)
                return
            connection_token = id
        except:
            await websocket.close(code=1008)
            return

    await websocket.accept()

    # handshake - 尝试接收握手消息
    try:
        # 首先尝试接收文本消息
        try:
            handshake_text = await websocket.receive_text()
            print(f"DEBUG: Received text handshake: {handshake_text[:100]}...")
            # 移除可能的记录分隔符
            if handshake_text.endswith('\x1e'):
                handshake_text = handshake_text[:-1]
            handshake_payload = json.loads(handshake_text)
        except KeyError:
            # WebSocket可能已经断开连接，无法接收消息
            print("DEBUG: WebSocket disconnected during handshake (no text)")
            return
        except WebSocketDisconnect:
            print("DEBUG: WebSocket disconnected during handshake")
            return
        except Exception:
            # 如果文本失败，尝试字节
            try:
                handshake_bytes = await websocket.receive_bytes()
                print(f"DEBUG: Received bytes handshake: {handshake_bytes[:50]}...")
                # 移除可能的记录分隔符
                if handshake_bytes.endswith(b'\x1e'):
                    handshake_bytes = handshake_bytes[:-1]
                handshake_payload = json.loads(handshake_bytes.decode())
            except (KeyError, WebSocketDisconnect):
                print("DEBUG: WebSocket disconnected during handshake (no bytes)")
                return
            except Exception as e:
                print(f"DEBUG: Failed to receive handshake as text or bytes: {e}")
                try:
                    await websocket.close(code=1002)  # Protocol error
                except:
                    pass  # WebSocket might already be closed
                return
    except Exception as e:
        print(f"DEBUG: Handshake processing error: {e}")
        try:
            await websocket.close(code=1002)  # Protocol error
        except:
            pass  # WebSocket might already be closed
        return

    error = ""

    # 检查协议支持
    protocol = handshake_payload.get("protocol")
    version = handshake_payload.get("version")

    if protocol not in ("messagepack", "json"):
        error = f"Requested protocol '{protocol}' is not available. Supported protocols: 'messagepack', 'json'."
    elif version != 1:
        error = f"Requested version '{version}' is not supported. Only version 1 is supported."

    hub_ = Hubs[hub]
    client = None
    try:
        client = hub_.add_client(
            connection_id=str(user.id),
            connection_token=connection_token,
            connection=websocket,
            protocol=protocol,
        )
    except TimeoutError:
        error = f"Connection {id} has waited too long."
    except ValueError as e:
        error = str(e)
    payload = {"error": error} if error else {}

    # finish handshake
    handshake_response = json.dumps(payload)
    try:
        if protocol == "json":
            # For JSON protocol, send handshake as text
            await websocket.send_text(handshake_response + '\x1e')
        else:
            # For MessagePack protocol, send handshake as bytes
            await websocket.send_bytes(handshake_response.encode() + SEP)
    except WebSocketDisconnect:
        print("DEBUG: WebSocket disconnected during handshake response")
        return
    except Exception as e:
        print(f"DEBUG: Error sending handshake response: {e}")
        return

    if error or not client:
        try:
            await websocket.close(code=1008)
        except:
            pass  # WebSocket might already be closed
        return

    # 发送欢迎消息给客户端
    try:
        # 所有hub都使用统一的欢迎消息方法
        await hub_.send_welcome_message(client)
        print(f"DEBUG: Sent welcome message to user {user.id} on {hub} hub")
    except Exception as e:
        print(f"DEBUG: Failed to send welcome message: {e}")

    # start listening for client messages
    try:
        await hub_._listen_client(client)
    except Exception as e:
        print(f"Error in client connection {user.id}: {e}")
    finally:
        # cleanup client connection
        await hub_.remove_client(connection_token)
