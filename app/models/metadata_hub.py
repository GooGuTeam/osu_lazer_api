from __future__ import annotations

from datetime import datetime
from enum import IntEnum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .signalr import MessagePackArrayModel


class UserStatus(MessagePackArrayModel):
    """用户状态 - 对应osu源码UserStatus"""
    type: str = "online"  # "online", "offline", "dnd", "away", "idle"
    description: Optional[str] = None


class UserActivity(MessagePackArrayModel):
    """用户活动基类 - 对应osu源码UserActivity"""
    type: str
    details: Optional[str] = None
    beatmap_id: Optional[int] = None
    ruleset_id: Optional[int] = None

    model_config = {"use_enum_values": True}


class UserPresence(MessagePackArrayModel):
    """用户在线状态 - 对应osu源码UserPresence"""
    activity: Optional[UserActivity] = None
    status: Optional[UserStatus] = None


class BeatmapUpdates(MessagePackArrayModel):
    """谱面更新信息 - 对应osu源码BeatmapUpdates"""
    beatmap_set_ids: List[int] = Field(alias="BeatmapSetIDs")
    last_processed_queue_id: int = Field(alias="LastProcessedQueueID")

    model_config = {"populate_by_name": True}


class DailyChallengeInfo(MessagePackArrayModel):
    """每日挑战信息 - 对应osu源码DailyChallengeInfo"""
    room_id: int = Field(alias="RoomID")

    model_config = {"populate_by_name": True}


class MultiplayerRoomScoreSetEvent(MessagePackArrayModel):
    """多人房间分数设置事件 - 对应osu源码MultiplayerRoomScoreSetEvent"""
    room_id: int = Field(alias="RoomID")
    playlist_item_id: int = Field(alias="PlaylistItemID")
    score_id: int = Field(alias="ScoreID")
    user_id: int = Field(alias="UserID")
    total_score: int = Field(alias="TotalScore")
    new_rank: Optional[int] = Field(alias="NewRank", default=None)

    model_config = {"populate_by_name": True}


class MultiplayerPlaylistItemStats(MessagePackArrayModel):
    """多人游戏播放列表项统计"""
    item_id: int
    play_count: int
    total_score_count: int
