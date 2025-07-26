from __future__ import annotations

import asyncio
import inspect
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
        self, connection_id: str, connection_token: str, connection: WebSocket, protocol: str = "messagepack"
    ) -> None:
        self.connection_id = connection_id
        self.connection_token = connection_token
        self.connection = connection
        self.protocol = protocol  # Store the protocol used by this client
        self._listen_task: asyncio.Task | None = None
        self._ping_task: asyncio.Task | None = None
        self._store = ResultStore()

    async def send_packet(self, type: PacketType, packet: list[Any]):
        packet.insert(0, type.value)

        if self.protocol == "json":
            # For JSON protocol, send as text using SignalR JSON object format
            import json

            # Convert MessagePack array format to SignalR JSON object format
            message_type = packet[0]  # PacketType value

            if message_type == PacketType.INVOCATION.value:
                # Invocation: [type, headers, invocationId, target, arguments, streamIds]
                signalr_message = {
                    "type": message_type,
                    "headers": packet[1] if len(packet) > 1 else {},
                    "target": packet[3] if len(packet) > 3 else None,
                    "arguments": packet[4] if len(packet) > 4 else [],
                    "streamIds": packet[5] if len(packet) > 5 and packet[5] is not None else []
                }
                # Only include invocationId if it's not None
                if len(packet) > 2 and packet[2] is not None:
                    signalr_message["invocationId"] = packet[2]
            elif message_type == PacketType.COMPLETION.value:
                # Completion: [type, headers, invocationId, result, error]
                signalr_message = {
                    "type": message_type,
                    "headers": packet[1] if len(packet) > 1 else {},
                }
                # Only include invocationId if it's not None
                if len(packet) > 2 and packet[2] is not None:
                    signalr_message["invocationId"] = packet[2]
                # Only include result OR error, never both (they are mutually exclusive)
                if len(packet) > 4 and packet[4] is not None:
                    # Error takes precedence
                    signalr_message["error"] = packet[4]
                elif len(packet) > 3 and packet[3] is not None:
                    # Only set result if no error
                    signalr_message["result"] = packet[3]
            elif message_type == PacketType.PING.value:
                # Ping: just type
                signalr_message = {"type": message_type}
            else:
                # For other types, create basic structure
                signalr_message = {"type": message_type}
                if len(packet) > 1:
                    signalr_message["headers"] = packet[1]

            payload = json.dumps(signalr_message) + '\x1e'  # Record separator
            await self.connection.send_text(payload)
        else:
            # For MessagePack protocol, send as binary
            payload = msgpack.packb(packet)
            if payload is not None:
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
        self, connection_id: str, connection_token: str, connection: WebSocket, protocol: str = "messagepack"
    ) -> Client:
        if connection_token in self.clients:
            raise ValueError(
                f"Client with connection token {connection_token} already exists."
            )

        # 检查waited_clients是可选的 - 如果存在则验证并清理，否则直接添加
        if connection_token in self.waited_clients:
            if (
                self.waited_clients[connection_token]
                < time.time() - settings.SIGNALR_NEGOTIATE_TIMEOUT
            ):
                raise TimeoutError(f"Connection {connection_id} has waited too long.")
            del self.waited_clients[connection_token]
        # 如果不在waited_clients中，说明是直接WebSocket连接（新的认证流程）

        client = Client(connection_id, connection_token, connection, protocol)
        self.clients[connection_token] = client
        task = asyncio.create_task(client._ping())
        self.tasks.add(task)
        client._ping_task = task
        return client

    async def remove_client(self, connection_token: str) -> None:
        if client := self.clients.get(connection_token):
            del self.clients[connection_token]
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
                if client.protocol == "json":
                    # For JSON protocol, receive text messages
                    message = await client.connection.receive_text()
                    # Remove record separator if present
                    if message.endswith('\x1e'):
                        message = message[:-1]

                    # Handle handshake message separately
                    if message.startswith('{"protocol"') and '"version"' in message:
                        # This is a handshake message, skip packet parsing
                        continue

                    # Parse JSON message
                    packet_type, packet_data = self._parse_json_packet(message)
                else:
                    # For MessagePack protocol, receive bytes messages
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
        await self.remove_client(client.connection_token)

    def _parse_json_packet(self, message: str) -> tuple[PacketType, list[Any]]:
        """Parse JSON SignalR message into packet type and data"""
        import json

        try:
            msg_data = json.loads(message)

            # Extract packet type
            packet_type = PacketType(msg_data.get("type", 0))

            # Convert JSON object back to array format for compatibility
            if packet_type == PacketType.INVOCATION:
                packet_data = [
                    msg_data.get("headers", {}),
                    msg_data.get("invocationId"),
                    msg_data.get("target"),
                    msg_data.get("arguments", []),
                    msg_data.get("streamIds", [])
                ]
            elif packet_type == PacketType.COMPLETION:
                packet_data = [
                    msg_data.get("headers", {}),
                    msg_data.get("invocationId"),
                    msg_data.get("result"),
                    msg_data.get("error")
                ]
            elif packet_type == PacketType.PING:
                packet_data = []
            else:
                # For other types, use basic structure
                packet_data = [msg_data.get("headers", {})]

            return packet_type, packet_data

        except (json.JSONDecodeError, ValueError) as e:
            print(f"Error parsing JSON packet: {e}")
            return PacketType.PING, []  # Return safe default

    async def _handle_packet(
        self, client: Client, type: PacketType, packet: list[Any]
    ) -> None:
        match type:
            case PacketType.PING:
                # 回应客户端的PING包
                await client.send_packet(PacketType.PING, [])
            case PacketType.INVOCATION:
                invocation_id = packet[1] if len(packet) > 1 else None
                target = packet[2] if len(packet) > 2 else ""
                args: list[Any] | None = packet[3] if len(packet) > 3 else None
                if args is None:
                    args = []
                # streams: list[str] | None = packet[4]  # TODO: stream support
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

                # Build completion packet correctly for SignalR protocol
                if code == ResultKind.ERROR:
                    # Error completion: [headers, invocationId, None, error]
                    packet = [
                        {},  # header
                        invocation_id,
                        None,  # result (must be None when there's an error)
                        result  # error message
                    ]
                elif code == ResultKind.HAS_VALUE:
                    # Success completion with result: [headers, invocationId, result, None]
                    packet = [
                        {},  # header
                        invocation_id,
                        result,  # result
                        None  # error (must be None when there's a result)
                    ]
                else:
                    # Void completion: [headers, invocationId, None, None]
                    packet = [
                        {},  # header
                        invocation_id,
                        None,  # result
                        None   # error
                    ]

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
        arg_index = 0

        for name, param in signature.parameters.items():
            # Skip 'self' parameter
            if name == "self":
                continue
            # Skip 'client' parameter - check by name since annotation checking is unreliable
            if name == "client":
                continue

            if arg_index >= len(args):
                raise InvokeException(f"Not enough arguments provided for method '{method}'. Expected at least {arg_index + 1} arguments, got {len(args)}.")

            # Handle different parameter types
            try:
                arg_value = args[arg_index]

                # Handle SignalR derived type workaround format
                if isinstance(arg_value, dict) and '$dtype' in arg_value and '$value' in arg_value:
                    # Convert SignalR derived type format to our expected format
                    dtype = arg_value['$dtype']
                    value = arg_value['$value']
                    print(f"DEBUG: Converting SignalR derived type: ${dtype} with value: {value}")

                    # Map SignalR activity types to our format
                    if hasattr(param.annotation, '__name__') and param.annotation.__name__ == 'UserActivity':
                        # For UserActivity, set type from $dtype and merge $value
                        converted_value = {'type': dtype}
                        if isinstance(value, dict):
                            converted_value.update(value)
                        arg_value = converted_value
                        print(f"DEBUG: Converted UserActivity to: {arg_value}")
                    else:
                        # For other types, use $value directly
                        arg_value = value
                        print(f"DEBUG: Using $value directly: {arg_value}")

                # Check if the parameter is a Pydantic model
                if (hasattr(param.annotation, '__bases__') and
                    any(base.__name__ == 'BaseModel' for base in param.annotation.__bases__)):
                    # It's a Pydantic model, validate it
                    call_params.append(param.annotation.model_validate(arg_value))
                elif param.annotation != inspect.Parameter.empty:
                    # Has type annotation but not a BaseModel
                    call_params.append(arg_value)
                else:
                    # No type annotation, pass as-is
                    call_params.append(arg_value)

            except Exception as e:
                # If validation fails, pass the argument as-is
                call_params.append(args[arg_index])

            arg_index += 1

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
                [],  # streams - 空数组而不是None
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
                [],  # streams - 空数组而不是None
            ],
        )
        return None

    async def send_welcome_message(self, client: Client) -> None:
        """发送欢迎消息给新连接的客户端 - 通用版本"""
        try:
            # 发送简单的欢迎消息
            await self.call_noblock(client, "UserMessage", "欢迎来到咕服！ Welcome to 咕 Server! 🎵")
        except Exception as e:
            print(f"Failed to send welcome message: {e}")

    def __contains__(self, item: str) -> bool:
        return item in self.clients or item in self.waited_clients
