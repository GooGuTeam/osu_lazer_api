from __future__ import annotations

from typing import Dict, Set, List

from app.models.metadata_hub import (
    BeatmapUpdates,
    DailyChallengeInfo,
    MultiplayerPlaylistItemStats,
    MultiplayerRoomScoreSetEvent,
    UserActivity,
    UserPresence,
    UserStatus,
)
from app.router.signalr.packet import PacketType

from .hub import Client, Hub


class MetadataHub(Hub):
    """元数据Hub - 实现IMetadataServer和IMetadataClient接口"""

    async def send_welcome_message(self, client: Client) -> None:
        """发送欢迎消息给新连接的客户端 - 元数据Hub专用版本"""
        # 元数据客户端不需要欢迎消息，只需要连接成功
        pass

    # TODO: 实现元数据相关的方法

    def __init__(self) -> None:
        super().__init__()
        # 用户在线状态存储 - key: user_id, value: UserPresence
        self.user_presences: Dict[int, UserPresence] = {}
        # 观看用户状态的订阅者 - set of user_ids
        self.presence_watchers: Set[int] = set()
        # 朋友在线状态 - key: user_id, value: UserPresence
        self.friend_presences: Dict[int, UserPresence] = {}
        # 观看多人房间的订阅者 - key: room_id, value: set of user_ids
        self.room_watchers: Dict[int, Set[int]] = {}
        # 每日挑战信息
        self.daily_challenge_info: DailyChallengeInfo | None = None
        # 谱面更新队列ID
        self.current_queue_id = 1

    # =============================================================================
    # IMetadataServer接口实现 - 客户端调用的方法
    # =============================================================================

    async def GetChangesSince(self, client: Client, queue_id: int) -> BeatmapUpdates:
        """获取自指定队列ID以来的变更"""
        # 简单实现：返回空的更新，增加队列ID
        return BeatmapUpdates(
            beatmap_set_ids=[],
            last_processed_queue_id=self.current_queue_id
        )

    async def UpdateActivity(self, client: Client, activity: UserActivity | None) -> None:
        """更新用户活动状态"""
        user_id = int(client.connection_id)

        # 更新或创建用户状态
        if user_id in self.user_presences:
            self.user_presences[user_id].activity = activity
        else:
            self.user_presences[user_id] = UserPresence(
                activity=activity,
                status=UserStatus(type="online")
            )

        # 通知所有观看用户状态的客户端
        await self._broadcast_user_presence_updated(user_id, self.user_presences[user_id])

    async def UpdateStatus(self, client: Client, status: UserStatus | None) -> None:
        """更新用户状态"""
        user_id = int(client.connection_id)

        # 更新或创建用户状态
        if user_id in self.user_presences:
            if status:
                self.user_presences[user_id].status = status
        else:
            self.user_presences[user_id] = UserPresence(
                activity=None,
                status=status or UserStatus(type="online")
            )

        # 通知所有观看用户状态的客户端
        await self._broadcast_user_presence_updated(user_id, self.user_presences[user_id])

    async def BeginWatchingUserPresence(self, client: Client) -> None:
        """开始观看用户在线状态"""
        user_id = int(client.connection_id)
        self.presence_watchers.add(user_id)

        # 发送当前所有用户的状态
        for presence_user_id, presence in self.user_presences.items():
            await self.call_noblock(client, "UserPresenceUpdated", presence_user_id, presence.model_dump())

    async def EndWatchingUserPresence(self, client: Client) -> None:
        """停止观看用户在线状态"""
        user_id = int(client.connection_id)
        self.presence_watchers.discard(user_id)

    async def BeginWatchingMultiplayerRoom(self, client: Client, room_id: int) -> List[MultiplayerPlaylistItemStats]:
        """开始观看多人房间"""
        user_id = int(client.connection_id)

        if room_id not in self.room_watchers:
            self.room_watchers[room_id] = set()
        self.room_watchers[room_id].add(user_id)

        # 返回房间的播放列表统计（简单实现：返回空列表）
        return []

    async def EndWatchingMultiplayerRoom(self, client: Client, room_id: int) -> None:
        """停止观看多人房间"""
        user_id = int(client.connection_id)

        if room_id in self.room_watchers:
            self.room_watchers[room_id].discard(user_id)
            if not self.room_watchers[room_id]:
                del self.room_watchers[room_id]

    # =============================================================================
    # IMetadataClient接口实现 - 服务器向客户端发送的方法
    # =============================================================================

    async def _broadcast_user_presence_updated(self, user_id: int, presence: UserPresence) -> None:
        """向所有观看用户状态的客户端广播用户状态更新"""
        for watcher_id in self.presence_watchers:
            if watcher_client := self._get_client_by_user_id(watcher_id):
                await self.call_noblock(watcher_client, "UserPresenceUpdated", user_id, presence.model_dump())

    async def broadcast_friend_presence_updated(self, user_id: int, presence: UserPresence | None) -> None:
        """广播朋友在线状态更新"""
        if presence:
            self.friend_presences[user_id] = presence
        else:
            self.friend_presences.pop(user_id, None)

        for client in self.clients.values():
            await self.call_noblock(client, "FriendPresenceUpdated", user_id, presence.model_dump() if presence else None)

    async def broadcast_beatmap_sets_updated(self, updates: BeatmapUpdates) -> None:
        """广播谱面集更新"""
        self.current_queue_id = updates.last_processed_queue_id

        for client in self.clients.values():
            await self.call_noblock(client, "BeatmapSetsUpdated", updates.model_dump())

    async def broadcast_daily_challenge_updated(self, info: DailyChallengeInfo | None) -> None:
        """广播每日挑战更新"""
        self.daily_challenge_info = info

        for client in self.clients.values():
            await self.call_noblock(client, "DailyChallengeUpdated", info.model_dump() if info else None)

    async def broadcast_multiplayer_room_score_set(self, event: MultiplayerRoomScoreSetEvent) -> None:
        """广播多人房间分数事件"""
        if event.room_id in self.room_watchers:
            for watcher_id in self.room_watchers[event.room_id]:
                if watcher_client := self._get_client_by_user_id(watcher_id):
                    await self.call_noblock(watcher_client, "MultiplayerRoomScoreSet", event.model_dump())

    # =============================================================================
    # 辅助方法
    # =============================================================================

    def _get_client_by_user_id(self, user_id: int) -> Client | None:
        """根据用户ID获取客户端"""
        for client in self.clients.values():
            try:
                if int(client.connection_id) == user_id:
                    return client
            except ValueError:
                continue
        return None

    async def remove_client(self, connection_token: str) -> None:
        """移除客户端时清理订阅关系"""
        if client := self.clients.get(connection_token):
            try:
                user_id = int(client.connection_id)

                # 清理用户状态观看订阅
                self.presence_watchers.discard(user_id)

                # 清理房间观看订阅
                for room_id in list(self.room_watchers.keys()):
                    self.room_watchers[room_id].discard(user_id)
                    if not self.room_watchers[room_id]:
                        del self.room_watchers[room_id]

                # 移除用户状态信息 - 标记为离线
                if user_id in self.user_presences:
                    self.user_presences[user_id].status = UserStatus(type="offline")
                    # 通知其他观看者该用户离线
                    await self._broadcast_user_presence_updated(user_id, self.user_presences[user_id])
                    # 一段时间后清理状态
                    # TODO: 可以添加定时器来清理离线用户状态

            except ValueError:
                # connection_id不是有效的用户ID
                pass

        await super().remove_client(connection_token)
