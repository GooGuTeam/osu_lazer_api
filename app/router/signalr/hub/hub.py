from __future__ import annotations

import asyncio
import time
from typing import Any

from app.config import settings
from app.router.signalr.exception import InvokeException
from app.router.signalr.packet import (
    PacketType,
    ResultKind,
    encode_varint,
    parse_packet,
)
from app.router.signalr.store import ResultStore
from app.router.signalr.utils import get_signature

from fastapi import WebSocket
import msgpack
from pydantic import BaseModel
from starlette.websockets import WebSocketDisconnect


class Client:
    def __init__(
        self, connection_id: str, connection_token: str, connection: WebSocket
    ) -> None:
        self.connection_id = connection_id
        self.connection_token = connection_token
        self.connection = connection
        self._listen_task: asyncio.Task | None = None
        self._ping_task: asyncio.Task | None = None
        self._store = ResultStore()

    async def send_packet(self, type: PacketType, packet: list[Any]):
        packet.insert(0, type.value)
        payload = msgpack.packb(packet)
        length = encode_varint(len(payload))
        await self.connection.send_bytes(length + payload)

    async def _ping(self):
        while True:
            try:
                await self.send_packet(PacketType.PING, [])
                await asyncio.sleep(settings.SIGNALR_PING_INTERVAL)
            except WebSocketDisconnect:
                break
            except Exception as e:
                print(f"Error in ping task for {self.connection_id}: {e}")
                break


class Hub:
    def __init__(self) -> None:
        self.clients: dict[str, Client] = {}
        self.waited_clients: dict[str, int] = {}
        self.tasks: set[asyncio.Task] = set()

    def add_waited_client(self, connection_token: str, timestamp: int) -> None:
        self.waited_clients[connection_token] = timestamp

    def add_client(
        self, connection_id: str, connection_token: str, connection: WebSocket
    ) -> Client:
        if connection_token in self.clients:
            raise ValueError(
                f"Client with connection token {connection_token} already exists."
            )
        if connection_token in self.waited_clients:
            if (
                self.waited_clients[connection_token]
                < time.time() - settings.SIGNALR_NEGOTIATE_TIMEOUT
            ):
                raise TimeoutError(f"Connection {connection_id} has waited too long.")
            del self.waited_clients[connection_token]
        client = Client(connection_id, connection_token, connection)
        self.clients[connection_token] = client
        task = asyncio.create_task(client._ping())
        self.tasks.add(task)
        client._ping_task = task
        return client

    async def remove_client(self, connection_id: str) -> None:
        if client := self.clients.get(connection_id):
            del self.clients[connection_id]
            if client._listen_task:
                client._listen_task.cancel()
            if client._ping_task:
                client._ping_task.cancel()
            await client.connection.close()

    async def send_packet(self, client: Client, type: PacketType, packet: list[Any]):
        await client.send_packet(type, packet)

    async def _listen_client(self, client: Client) -> None:
        jump = False
        while not jump:
            try:
                message = await client.connection.receive_bytes()
                packet_type, packet_data = parse_packet(message)
                task = asyncio.create_task(
                    self._handle_packet(client, packet_type, packet_data)
                )
                self.tasks.add(task)
                task.add_done_callback(self.tasks.discard)
            except WebSocketDisconnect as e:
                if e.code == 1005:
                    continue
                print(
                    f"Client {client.connection_id} disconnected: {e.code}, {e.reason}"
                )
                jump = True
            except Exception as e:
                print(f"Error in client {client.connection_id}: {e}")
                jump = True
        await self.remove_client(client.connection_id)

    async def _handle_packet(
        self, client: Client, type: PacketType, packet: list[Any]
    ) -> None:
        match type:
            case PacketType.PING:
                ...
            case PacketType.INVOCATION:
                invocation_id: str | None = packet[1]  # pyright: ignore[reportRedeclaration]
                target: str = packet[2]
                args: list[Any] | None = packet[3]
                if args is None:
                    args = []
                streams: list[str] | None = packet[4]  # TODO: stream support
                code = ResultKind.VOID
                result = None
                try:
                    result = await self.invoke_method(client, target, args)
                    if result is not None:
                        code = ResultKind.HAS_VALUE
                except InvokeException as e:
                    code = ResultKind.ERROR
                    result = e.message

                except Exception as e:
                    code = ResultKind.ERROR
                    result = str(e)

                packet = [
                    {},  # header
                    invocation_id,
                    code.value,
                ]
                if result is not None:
                    packet.append(result)
                if invocation_id is not None:
                    await client.send_packet(
                        PacketType.COMPLETION,
                        packet,
                    )
            case PacketType.COMPLETION:
                invocation_id: str = packet[1]
                code: ResultKind = ResultKind(packet[2])
                result: Any = packet[3] if len(packet) > 3 else None
                client._store.add_result(invocation_id, code, result)

    async def invoke_method(self, client: Client, method: str, args: list[Any]) -> Any:
        method_ = getattr(self, method, None)
        call_params = []
        if not method_:
            raise InvokeException(f"Method '{method}' not found in hub.")
        signature = get_signature(method_)
        for name, param in signature.parameters.items():
            if name == "self" or param.annotation is Client:
                continue
            if issubclass(param.annotation, BaseModel):
                call_params.append(param.annotation.model_validate(args.pop(0)))
            else:
                call_params.append(args.pop(0))
        return await method_(client, *call_params)

    async def call(self, client: Client, method: str, *args: Any) -> Any:
        invocation_id = client._store.get_invocation_id()
        await client.send_packet(
            PacketType.INVOCATION,
            [
                {},  # header
                invocation_id,
                method,
                list(args),
                None,  # streams
            ],
        )
        r = await client._store.fetch(invocation_id, None)
        if r[0] == ResultKind.HAS_VALUE:
            return r[1]
        if r[0] == ResultKind.ERROR:
            raise InvokeException(r[1])
        return None

    async def call_noblock(self, client: Client, method: str, *args: Any) -> None:
        await client.send_packet(
            PacketType.INVOCATION,
            [
                {},  # header
                None,  # invocation_id
                method,
                list(args),
                None,  # streams
            ],
        )
        return None

    def __contains__(self, item: str) -> bool:
        return item in self.clients or item in self.waited_clients
