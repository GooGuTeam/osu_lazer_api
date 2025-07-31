from __future__ import annotations

from enum import IntEnum

from pydantic import BaseModel


class BeatmapRankStatus(IntEnum):
    GRAVEYARD = -2
    WIP = -1
    PENDING = 0
    RANKED = 1
    APPROVED = 2
    QUALIFIED = 3
    LOVED = 4


class Genre(IntEnum):
    ANY = 0
    UNSPECIFIED = 1
    VIDEO_GAME = 2
    ANIME = 3
    ROCK = 4
    POP = 5
    OTHER = 6
    NOVELTY = 7
    HIP_HOP = 9
    ELECTRONIC = 10
    METAL = 11
    CLASSICAL = 12
    FOLK = 13
    JAZZ = 14


class Language(IntEnum):
    ANY = 0
    UNSPECIFIED = 1
    ENGLISH = 2
    JAPANESE = 3
    CHINESE = 4
    INSTRUMENTAL = 5
    KOREAN = 6
    FRENCH = 7
    GERMAN = 8
    SWEDISH = 9
    ITALIAN = 10
    SPANISH = 11
    RUSSIAN = 12
    POLISH = 13
    OTHER = 14


class BeatmapAttributes(BaseModel):
    star_rating: float
    max_combo: int

    # osu
    aim_difficulty: float | None = None
    aim_difficult_slider_count: float | None = None
    speed_difficulty: float | None = None
    speed_note_count: float | None = None
    slider_factor: float | None = None
    aim_difficult_strain_count: float | None = None
    speed_difficult_strain_count: float | None = None

    # taiko
    mono_stamina_factor: float | None = None
