from __future__ import annotations

import datetime
from enum import IntEnum
from typing import Any

import msgpack
from pydantic import Field, field_validator

from .signalr import MessagePackArrayModel
from .score import (
    APIMod as APIModBase,
    HitResult,
)


class APIMod(APIModBase, MessagePackArrayModel): ...


class SpectatedUserState(IntEnum):
    Idle = 0
    Playing = 1
    Paused = 2
    Passed = 3
    Failed = 4
    Quit = 5


class SpectatorState(MessagePackArrayModel):
    beatmap_id: int | None = None
    ruleset_id: int | None = None  # 0,1,2,3
    mods: list[APIMod] = Field(default_factory=list)
    state: SpectatedUserState
    maximum_statistics: dict[HitResult, int] = Field(default_factory=dict)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SpectatorState):
            return False
        return (
            self.beatmap_id == other.beatmap_id
            and self.ruleset_id == other.ruleset_id
            and self.mods == other.mods
            and self.state == other.state
        )


class ScoreProcessorStatistics(MessagePackArrayModel):
    base_score: int
    maximum_base_score: int
    accuracy_judgement_count: int
    combo_portion: float
    bouns_portion: float


class FrameHeader(MessagePackArrayModel):
    total_score: int
    acc: float
    combo: int
    max_combo: int
    statistics: dict[HitResult, int] = Field(default_factory=dict)
    score_processor_statistics: ScoreProcessorStatistics
    received_time: datetime.datetime
    mods: list[APIMod] = Field(default_factory=list)

    @field_validator("received_time", mode="before")
    @classmethod
    def validate_timestamp(cls, v: Any) -> datetime.datetime:
        if isinstance(v, msgpack.ext.Timestamp):
            return v.to_datetime()
        if isinstance(v, list):
            return v[0].to_datetime()
        if isinstance(v, datetime.datetime):
            return v
        if isinstance(v, int | float):
            return datetime.datetime.fromtimestamp(v, tz=datetime.UTC)
        if isinstance(v, str):
            return datetime.datetime.fromisoformat(v)
        raise ValueError(f"Cannot convert {type(v)} to datetime")


class ReplayButtonState(IntEnum):
    NONE = 0
    LEFT1 = 1
    RIGHT1 = 2
    LEFT2 = 4
    RIGHT2 = 8
    SMOKE = 16


class LegacyReplayFrame(MessagePackArrayModel):
    time: int  # from ReplayFrame,the parent of LegacyReplayFrame
    x: float | None = None
    y: float | None = None
    button_state: ReplayButtonState


class FrameDataBundle(MessagePackArrayModel):
    header: FrameHeader
    frames: list[LegacyReplayFrame]
