from __future__ import annotations

from typing import Dict, Set, List, Optional

from app.models.spectator_hub import (
    SpectatorState,
    FrameDataBundle,
    SpectatorUser,
    SpectatedUserState,
)

from .hub import Client, Hub


class SpectatorHub(Hub):
    """观察者Hub - 实现ISpectatorServer和ISpectatorClient接口"""

    def __init__(self) -> None:
        super().__init__()
        # 用户状态存储 - key: user_id, value: SpectatorState
        self.user_states: Dict[int, SpectatorState] = {}
        # 观察关系存储 - key: user_id, value: set of watcher_user_ids
        self.watchers: Dict[int, Set[int]] = {}
        # 被观察关系存储 - key: watcher_user_id, value: set of watched_user_ids
        self.watching: Dict[int, Set[int]] = {}
        # 用户信息存储
        self.users: Dict[int, SpectatorUser] = {}

    # =============================================================================
    # ISpectatorServer接口实现 - 客户端调用的方法
    # =============================================================================

    async def BeginPlaySession(self, client: Client, score_token: Optional[int], state: SpectatorState) -> None:
        """开始游戏会话"""
        user_id = int(client.connection_id)

        # 更新用户状态
        self.user_states[user_id] = state

        # 通知所有观察者用户开始游戏
        if user_id in self.watchers:
            for watcher_id in self.watchers[user_id]:
                if watcher_client := self._get_client_by_user_id(watcher_id):
                    await self.call_noblock(watcher_client, "UserBeganPlaying", user_id, state.model_dump())

    async def SendFrameData(self, client: Client, data: FrameDataBundle) -> None:
        """发送帧数据"""
        user_id = int(client.connection_id)

        # 转发帧数据给所有观察者
        if user_id in self.watchers:
            for watcher_id in self.watchers[user_id]:
                if watcher_client := self._get_client_by_user_id(watcher_id):
                    await self.call_noblock(watcher_client, "UserSentFrames", user_id, data.model_dump())

    async def EndPlaySession(self, client: Client, state: SpectatorState) -> None:
        """结束游戏会话"""
        user_id = int(client.connection_id)

        # 更新用户状态
        self.user_states[user_id] = state

        # 通知所有观察者用户结束游戏
        if user_id in self.watchers:
            for watcher_id in self.watchers[user_id]:
                if watcher_client := self._get_client_by_user_id(watcher_id):
                    await self.call_noblock(watcher_client, "UserFinishedPlaying", user_id, state.model_dump())

    async def StartWatchingUser(self, client: Client, target_user_id: int) -> None:
        """开始观察用户"""
        watcher_id = int(client.connection_id)

        # 添加观察关系
        if target_user_id not in self.watchers:
            self.watchers[target_user_id] = set()
        self.watchers[target_user_id].add(watcher_id)

        if watcher_id not in self.watching:
            self.watching[watcher_id] = set()
        self.watching[watcher_id].add(target_user_id)

        # 如果目标用户正在游戏，发送当前状态
        if target_user_id in self.user_states:
            state = self.user_states[target_user_id]
            if state.state in [SpectatedUserState.Playing, SpectatedUserState.Paused]:
                await self.call_noblock(client, "UserBeganPlaying", target_user_id, state.model_dump())

        # 通知被观察的用户有新的观察者
        if target_client := self._get_client_by_user_id(target_user_id):
            watcher_user = self._get_user_info(watcher_id)
            if watcher_user:
                await self.call_noblock(target_client, "UserStartedWatching", [watcher_user.model_dump()])

    async def EndWatchingUser(self, client: Client, target_user_id: int) -> None:
        """停止观察用户"""
        watcher_id = int(client.connection_id)

        # 移除观察关系
        if target_user_id in self.watchers:
            self.watchers[target_user_id].discard(watcher_id)
            if not self.watchers[target_user_id]:
                del self.watchers[target_user_id]

        if watcher_id in self.watching:
            self.watching[watcher_id].discard(target_user_id)
            if not self.watching[watcher_id]:
                del self.watching[watcher_id]

        # 通知被观察的用户观察者离开
        if target_client := self._get_client_by_user_id(target_user_id):
            await self.call_noblock(target_client, "UserEndedWatching", watcher_id)

    # =============================================================================
    # ISpectatorClient接口实现 - 服务器向客户端发送的方法
    # =============================================================================

    async def notify_user_score_processed(self, user_id: int, score_id: int) -> None:
        """通知用户分数已处理"""
        # 通知所有观察该用户的客户端
        if user_id in self.watchers:
            for watcher_id in self.watchers[user_id]:
                if watcher_client := self._get_client_by_user_id(watcher_id):
                    await self.call_noblock(watcher_client, "UserScoreProcessed", user_id, score_id)

    # =============================================================================
    # 辅助方法
    # =============================================================================

    async def send_welcome_message(self, client: Client) -> None:
        """发送欢迎消息给新连接的客户端 - 观察者Hub专用版本"""
        # 观察者客户端不需要欢迎消息，只需要连接成功
        # 如果需要，可以在这里发送观察者特定的初始化消息
        pass

    def _get_client_by_user_id(self, user_id: int) -> Client | None:
        """根据用户ID获取客户端"""
        for client in self.clients.values():
            try:
                if int(client.connection_id) == user_id:
                    return client
            except ValueError:
                continue
        return None

    def _get_user_info(self, user_id: int) -> SpectatorUser | None:
        """获取用户信息"""
        # 简单实现：返回基本用户信息
        if user_id in self.users:
            return self.users[user_id]

        # 如果没有缓存，创建基本信息
        user_info = SpectatorUser(
            user_id=user_id,
            username=f"User{user_id}",
            country_code="XX",
            global_rank=None
        )
        self.users[user_id] = user_info
        return user_info

    async def remove_client(self, connection_token: str) -> None:
        """移除客户端时清理观察关系"""
        if client := self.clients.get(connection_token):
            try:
                user_id = int(client.connection_id)

                # 清理该用户正在观察的其他用户
                if user_id in self.watching:
                    for target_user_id in list(self.watching[user_id]):
                        await self.EndWatchingUser(client, target_user_id)

                # 清理观察该用户的其他用户
                if user_id in self.watchers:
                    for watcher_id in list(self.watchers[user_id]):
                        if watcher_client := self._get_client_by_user_id(watcher_id):
                            await self.EndWatchingUser(watcher_client, user_id)

                # 清理用户状态（标记为空闲）
                if user_id in self.user_states:
                    self.user_states[user_id].state = SpectatedUserState.Idle
                    # 可以选择保留状态一段时间或立即删除
                    # del self.user_states[user_id]

            except ValueError:
                # connection_id不是有效的用户ID
                pass

        await super().remove_client(connection_token)
