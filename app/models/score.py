from enum import Enum, IntEnum
from typing import Any
from pydantic import BaseModel

class GameMode(str, Enum):
    OSU = "osu"
    TAIKO = "taiko"
    FRUITS = "fruits"
    MANIA = "mania"

class APIMod(BaseModel):
    acronym: str
    settings: dict[str, Any] = {}

# https://github.com/ppy/osu/blob/master/osu.Game/Rulesets/Scoring/HitResult.cs
class HitResult(IntEnum):
    PERFECT = 0  # [Order(0)]
    GREAT = 1  # [Order(1)]
    GOOD = 2  # [Order(2)]
    OK = 3  # [Order(3)]
    MEH = 4  # [Order(4)]
    MISS = 5  # [Order(5)]

    LARGE_TICK_HIT = 6  # [Order(6)]
    SMALL_TICK_HIT = 7  # [Order(7)]
    SLIDER_TAIL_HIT = 8  # [Order(8)]

    LARGE_BONUS = 9  # [Order(9)]
    SMALL_BONUS = 10  # [Order(10)]

    LARGE_TICK_MISS = 11  # [Order(11)]
    SMALL_TICK_MISS = 12  # [Order(12)]

    IGNORE_HIT = 13  # [Order(13)]
    IGNORE_MISS = 14  # [Order(14)]

    NONE = 15  # [Order(15)]
    COMBO_BREAK = 16  # [Order(16)]

    LEGACY_COMBO_INCREASE = 99  # [Order(99)] @deprecated
