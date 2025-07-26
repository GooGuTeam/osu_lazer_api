from __future__ import annotations

from typing import Any

from app.models.multiplayer_hub import (
    MatchUserRequest,
    MultiplayerPlaylistItem,
    MultiplayerRoom,
    MultiplayerRoomState,
    MultiplayerRoomUser,
    MatchUserState,
)
from app.router.signalr.packet import PacketType

from .hub import Client, Hub


class MultiplayerHub(Hub):
    """多人游戏Hub - 实现IMultiplayerServer和IMultiplayerClient接口"""

    async def send_welcome_message(self, client: Client) -> None:
        """发送欢迎消息给新连接的客户端 - 多人游戏Hub专用版本"""
        # 多人游戏客户端不需要欢迎消息，只需要连接成功
        pass

    # TODO: 实现多人游戏相关的方法
    def __init__(self) -> None:
        super().__init__()
        # 房间信息存储
        self.rooms: dict[int, MultiplayerRoom] = {}
        # 用户所在房间映射
        self.user_rooms: dict[int, int] = {}  # user_id -> room_id

    # IMultiplayerLoungeServer methods
    async def CreateRoom(self, client: Client, room: MultiplayerRoom) -> MultiplayerRoom:
        """创建多人房间"""
        user_id = int(client.connection_id)

        # 检查用户是否已在房间中
        if user_id in self.user_rooms:
            raise ValueError("User is already in a room")

        # 设置房主
        host_user = MultiplayerRoomUser(
            user_id=user_id,
            username=f"User{user_id}",  # 简化实现
            state=MatchUserState.Idle,
            mods=[]
        )
        room.host = host_user
        room.users = [host_user]

        # 存储房间
        self.rooms[room.room_id] = room
        self.user_rooms[user_id] = room.room_id

        return room

    async def JoinRoom(self, client: Client, room_id: int) -> MultiplayerRoom:
        """加入多人房间"""
        user_id = int(client.connection_id)

        # 检查用户是否已在房间中
        if user_id in self.user_rooms:
            raise ValueError("User is already in a room")

        # 检查房间是否存在
        if room_id not in self.rooms:
            raise ValueError("Room does not exist")

        room = self.rooms[room_id]

        # 检查房间是否已满
        if len(room.users) >= room.settings.max_participants:
            raise ValueError("Room is full")

        # 添加用户到房间
        new_user = MultiplayerRoomUser(
            user_id=user_id,
            username=f"User{user_id}",  # 简化实现
            state=MatchUserState.Idle,
            mods=[]
        )
        room.users.append(new_user)
        self.user_rooms[user_id] = room_id

        # 通知房间内其他用户
        await self._broadcast_to_room(room_id, "UserJoined", new_user.model_dump(), exclude_user=user_id)

        return room

    async def JoinRoomWithPassword(self, client: Client, room_id: int, password: str) -> MultiplayerRoom:
        """使用密码加入多人房间"""
        # 简化实现：暂时不验证密码
        return await self.JoinRoom(client, room_id)

    # IMultiplayerRoomServer methods
    async def LeaveRoom(self, client: Client) -> None:
        """离开当前房间"""
        user_id = int(client.connection_id)

        if user_id not in self.user_rooms:
            raise ValueError("User is not in a room")

        room_id = self.user_rooms[user_id]
        room = self.rooms[room_id]

        # 找到并移除用户
        user_to_remove = None
        for user in room.users:
            if user.user_id == user_id:
                user_to_remove = user
                break

        if user_to_remove:
            room.users.remove(user_to_remove)
            del self.user_rooms[user_id]

            # 通知房间内其他用户
            await self._broadcast_to_room(room_id, "UserLeft", user_to_remove.model_dump())

            # 如果是房主离开，转移房主权限
            if room.host and room.host.user_id == user_id:
                if room.users:
                    room.host = room.users[0]
                    await self._broadcast_to_room(room_id, "HostChanged", room.host.model_dump())
                else:
                    # 房间空了，删除房间
                    del self.rooms[room_id]

    async def TransferHost(self, client: Client, user_id: int) -> None:
        """转移房主权限"""
        current_user_id = int(client.connection_id)

        if current_user_id not in self.user_rooms:
            raise ValueError("User is not in a room")

        room_id = self.user_rooms[current_user_id]
        room = self.rooms[room_id]

        # 检查是否为房主
        if not room.host or room.host.user_id != current_user_id:
            raise ValueError("User is not the host")

        # 找到目标用户
        new_host = None
        for user in room.users:
            if user.user_id == user_id:
                new_host = user
                break

        if not new_host:
            raise ValueError("Target user not in room")

        room.host = new_host
        await self._broadcast_to_room(room_id, "HostChanged", new_host.model_dump())

    async def KickUser(self, client: Client, user_id: int) -> None:
        """踢出用户"""
        current_user_id = int(client.connection_id)

        if current_user_id not in self.user_rooms:
            raise ValueError("User is not in a room")

        room_id = self.user_rooms[current_user_id]
        room = self.rooms[room_id]

        # 检查是否为房主
        if not room.host or room.host.user_id != current_user_id:
            raise ValueError("User is not the host")

        # 找到并移除目标用户
        user_to_kick = None
        for user in room.users:
            if user.user_id == user_id:
                user_to_kick = user
                break

        if user_to_kick:
            room.users.remove(user_to_kick)
            if user_id in self.user_rooms:
                del self.user_rooms[user_id]

            # 通知房间内所有用户（包括被踢的用户）
            await self._broadcast_to_room(room_id, "UserKicked", user_to_kick.model_dump())

            # 单独通知被踢的用户
            if kicked_client := self._get_client_by_user_id(user_id):
                await self.send_packet(
                    kicked_client,
                    PacketType.INVOCATION,
                    ["UserKicked", user_to_kick.model_dump()]
                )

    async def SendMatchRequest(self, client: Client, request: MatchUserRequest) -> None:
        """发送匹配请求"""
        user_id = int(client.connection_id)

        if user_id not in self.user_rooms:
            raise ValueError("User is not in a room")

        room_id = self.user_rooms[user_id]

        # 广播请求到房间内所有用户
        await self._broadcast_to_room(room_id, "MatchUserRequest", request.model_dump())

    async def StartMatch(self, client: Client) -> None:
        """开始匹配"""
        user_id = int(client.connection_id)

        if user_id not in self.user_rooms:
            raise ValueError("User is not in a room")

        room_id = self.user_rooms[user_id]
        room = self.rooms[room_id]

        # 检查是否为房主
        if not room.host or room.host.user_id != user_id:
            raise ValueError("User is not the host")

        # 更改房间状态
        room.state = MultiplayerRoomState.Playing

        # 通知房间内所有用户
        await self._broadcast_to_room(room_id, "RoomStateChanged", room.state.value)

    async def AbortMatch(self, client: Client) -> None:
        """中止匹配"""
        user_id = int(client.connection_id)

        if user_id not in self.user_rooms:
            raise ValueError("User is not in a room")

        room_id = self.user_rooms[user_id]
        room = self.rooms[room_id]

        # 检查是否为房主
        if not room.host or room.host.user_id != user_id:
            raise ValueError("User is not the host")

        # 更改房间状态
        room.state = MultiplayerRoomState.Open

        # 通知房间内所有用户
        await self._broadcast_to_room(room_id, "RoomStateChanged", room.state.value)

    async def AbortGameplay(self, client: Client) -> None:
        """中止游戏"""
        # 简化实现：与中止匹配相同
        await self.AbortMatch(client)

    async def AddPlaylistItem(self, client: Client, item: MultiplayerPlaylistItem) -> None:
        """添加播放列表项"""
        user_id = int(client.connection_id)

        if user_id not in self.user_rooms:
            raise ValueError("User is not in a room")

        room_id = self.user_rooms[user_id]
        room = self.rooms[room_id]

        room.playlist.append(item)

        # 通知房间内所有用户
        await self._broadcast_to_room(room_id, "PlaylistItemAdded", item.model_dump())

    async def EditPlaylistItem(self, client: Client, item: MultiplayerPlaylistItem) -> None:
        """编辑播放列表项"""
        user_id = int(client.connection_id)

        if user_id not in self.user_rooms:
            raise ValueError("User is not in a room")

        room_id = self.user_rooms[user_id]
        room = self.rooms[room_id]

        # 找到并更新项目
        for i, existing_item in enumerate(room.playlist):
            if existing_item.id == item.id:
                room.playlist[i] = item
                break

        # 通知房间内所有用户
        await self._broadcast_to_room(room_id, "PlaylistItemChanged", item.model_dump())

    async def RemovePlaylistItem(self, client: Client, playlist_item_id: int) -> None:
        """移除播放列表项"""
        user_id = int(client.connection_id)

        if user_id not in self.user_rooms:
            raise ValueError("User is not in a room")

        room_id = self.user_rooms[user_id]
        room = self.rooms[room_id]

        # 找到并移除项目
        item_to_remove = None
        for item in room.playlist:
            if item.id == playlist_item_id:
                item_to_remove = item
                break

        if item_to_remove:
            room.playlist.remove(item_to_remove)

            # 通知房间内所有用户
            await self._broadcast_to_room(room_id, "PlaylistItemRemoved", playlist_item_id)

    async def _broadcast_to_room(self, room_id: int, method: str, data: Any, exclude_user: int | None = None) -> None:
        """向房间内所有用户广播消息"""
        if room_id not in self.rooms:
            return

        room = self.rooms[room_id]
        for user in room.users:
            if exclude_user and user.user_id == exclude_user:
                continue

            if client := self._get_client_by_user_id(user.user_id):
                await self.send_packet(
                    client,
                    PacketType.INVOCATION,
                    [method, data]
                )

    def _get_client_by_user_id(self, user_id: int) -> Client | None:
        """根据用户ID获取客户端"""
        for client in self.clients.values():
            if int(client.connection_id) == user_id:
                return client
        return None

    async def remove_client(self, connection_token: str) -> None:
        """移除客户端时清理房间关系"""
        if client := self.clients.get(connection_token):
            user_id = int(client.connection_id)

            # 如果用户在房间中，自动离开
            if user_id in self.user_rooms:
                try:
                    await self.LeaveRoom(client)
                except:
                    # 忽略离开房间时的错误
                    pass

        await super().remove_client(connection_token)
