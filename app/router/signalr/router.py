from __future__ import annotations

import json
from logging import info
import time
from typing import Literal
import uuid

from app.database import User as DBUser
from app.dependencies import get_current_user
from app.dependencies.database import get_db
from app.dependencies.user import get_current_user_by_token, security
from app.models.signalr import NegotiateResponse, Transport
from app.router.signalr.packet import SEP

from .hub import Hubs

from fastapi import APIRouter, Depends, Header, Query, WebSocket
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

router = APIRouter()


@router.post("/{hub}/negotiate", response_model=NegotiateResponse)
async def negotiate(
    hub: Literal["spectator", "multiplayer", "metadata"],
    negotiate_version: int = Query(1, alias="negotiateVersion"),
    user: DBUser = Depends(get_current_user),
):
    connectionId = str(user.id)
    connectionToken = f"{connectionId}:{uuid.uuid4()}"
    Hubs[hub].add_waited_client(
        connection_token=connectionToken,
        timestamp=int(time.time()),
    )
    return NegotiateResponse(
        connectionId=connectionId,
        connectionToken=connectionToken,
        negotiateVersion=negotiate_version,
        availableTransports=[Transport(transport="WebSockets")],
    )


@router.websocket("/{hub}")
async def connect(
    hub: Literal["spectator", "multiplayer", "metadata"],
    websocket: WebSocket,
    id: str,
    authorization: str = Header(...),
    db: Session = Depends(get_db),
):
    token = authorization[7:]
    user_id = id.split(":")[0]
    hub_ = Hubs[hub]
    if id not in hub_:
        await websocket.close(code=1008)
        return
    if (user := await get_current_user_by_token(token, db)) is None or str(
        user.id
    ) != user_id:
        await websocket.close(code=1008)
        return
    await websocket.accept()

    # handshake
    handshake = await websocket.receive_bytes()
    handshake_payload = json.loads(handshake[:-1])
    error = ""
    if (protocol := handshake_payload.get("protocol")) != "messagepack" or (
        handshake_payload.get("version")
    ) != 1:
        error = f"Requested protocol '{protocol}' is not available."

    client = None
    try:
        client = hub_.add_client(
            connection_id=user_id,
            connection_token=id,
            connection=websocket,
        )
    except TimeoutError:
        error = f"Connection {id} has waited too long."
    except ValueError as e:
        error = str(e)
    payload = {"error": error} if error else {}

    # finish handshake
    await websocket.send_bytes(json.dumps(payload).encode() + SEP)
    if error or not client:
        await websocket.close(code=1008)
        return
    await hub_._listen_client(client)
