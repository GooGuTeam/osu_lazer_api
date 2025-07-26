from __future__ import annotations

from datetime import datetime
from enum import IntEnum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .signalr import MessagePackArrayModel


class SpectatedUserState(IntEnum):
    """观察用户状态枚举"""
    Idle = 0
    WaitingForLoad = 1
    Playing = 2
    Paused = 3
    Passed = 4
    Failed = 5
    Quit = 6


class HitResult(IntEnum):
    """命中结果枚举"""
    None_ = 0
    Miss = 1
    Meh = 2
    Ok = 3
    Good = 4
    Great = 5
    Perfect = 6
    SmallTickMiss = 7
    SmallTickHit = 8
    LargeTickMiss = 9
    LargeTickHit = 10
    SmallBonus = 11
    LargeBonus = 12
    IgnoreMiss = 13
    IgnoreHit = 14
    ComboBreak = 15


class APIMod(MessagePackArrayModel):
    """API模组"""
    acronym: str
    settings: Optional[Dict[str, Any]] = None


class SpectatorState(MessagePackArrayModel):
    """观察者状态"""
    beatmap_id: Optional[int] = Field(alias="BeatmapID", default=None)
    ruleset_id: Optional[int] = Field(alias="RulesetID", default=None)
    mods: List[APIMod] = Field(alias="Mods", default_factory=list)
    state: SpectatedUserState = Field(alias="State", default=SpectatedUserState.Idle)
    maximum_statistics: Dict[int, int] = Field(alias="MaximumStatistics", default_factory=dict)
    
    model_config = {"populate_by_name": True}


class LegacyReplayFrame(MessagePackArrayModel):
    """Legacy回放帧"""
    time: float
    mouse_x: Optional[float] = None
    mouse_y: Optional[float] = None
    button_state: int = 0


class ScoreProcessorStatistics(MessagePackArrayModel):
    """分数处理器统计"""
    max_combo_sources: int = 0
    combo_sources: int = 0
    basic_hit_objects: int = 0
    max_basic_hit_objects: int = 0


class FrameHeader(MessagePackArrayModel):
    """帧头信息"""
    total_score: int = Field(alias="TotalScore", default=0)
    accuracy: float = Field(alias="Accuracy", default=0.0)
    combo: int = Field(alias="Combo", default=0)
    max_combo: int = Field(alias="MaxCombo", default=0)
    statistics: Dict[int, int] = Field(alias="Statistics", default_factory=dict)
    score_processor_statistics: ScoreProcessorStatistics = Field(alias="ScoreProcessorStatistics", default_factory=ScoreProcessorStatistics)
    received_time: datetime = Field(alias="ReceivedTime", default_factory=datetime.utcnow)
    
    model_config = {"populate_by_name": True}


class FrameDataBundle(MessagePackArrayModel):
    """帧数据包"""
    header: FrameHeader = Field(alias="Header")
    frames: List[LegacyReplayFrame] = Field(alias="Frames", default_factory=list)
    
    model_config = {"populate_by_name": True}


class SpectatorUser(MessagePackArrayModel):
    """观察者用户信息"""
    user_id: int
    username: str
    country_code: Optional[str] = None
    global_rank: Optional[int] = None
