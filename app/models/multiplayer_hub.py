from __future__ import annotations

from datetime import datetime
from enum import IntEnum
from typing import Any, Optional

from pydantic import BaseModel

from .signalr import MessagePackArrayModel
from .spectator_hub import APIMod


class MultiplayerRoomState(IntEnum):
    """多人房间状态"""
    Open = 0
    Playing = 1
    Closed = 2


class MatchUserState(IntEnum):
    """匹配用户状态"""
    Idle = 0
    Ready = 1
    WaitingForLoad = 2
    Loaded = 3
    Playing = 4
    FinishedPlay = 5
    Results = 6
    Quit = 7


class MultiplayerRoomUser(MessagePackArrayModel):
    """多人房间用户"""
    user_id: int
    username: str
    state: MatchUserState
    mods: list[APIMod]
    beatmap_availability_state: int = 0  # 0: Available, 1: NotDownloaded, 2: Downloading, etc.


class MultiplayerRoomSettings(MessagePackArrayModel):
    """多人房间设置"""
    name: str
    password: Optional[str] = None
    max_participants: int = 16
    queue_mode: int = 0  # 0: All, 1: Host


class MultiplayerPlaylistItem(MessagePackArrayModel):
    """多人播放列表项"""
    id: int
    beatmap_id: int
    beatmap_checksum: str
    ruleset_id: int
    required_mods: list[APIMod]
    allowed_mods: list[APIMod]
    expired: bool = False


class MultiplayerCountdown(MessagePackArrayModel):
    """多人倒计时"""
    id: int
    start_time: datetime
    duration: float  # seconds


class MatchRoomState(MessagePackArrayModel):
    """匹配房间状态"""
    room_id: int
    beatmap_id: int
    beatmap_checksum: str


class MultiplayerRoom(MessagePackArrayModel):
    """多人房间"""
    room_id: int
    state: MultiplayerRoomState
    settings: MultiplayerRoomSettings
    users: list[MultiplayerRoomUser]
    host: Optional[MultiplayerRoomUser] = None
    match_state: Optional[MatchRoomState] = None
    playlist: list[MultiplayerPlaylistItem]
    active_countdowns: list[MultiplayerCountdown]


class MatchUserRequest(MessagePackArrayModel):
    """匹配用户请求"""
    type: str
    data: dict[str, Any]
