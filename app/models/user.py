from __future__ import annotations

from datetime import datetime
from enum import Enum

from app.database import (
    LazerUserAchievement,
    Team as Team,
)

from .score import GameMode

from pydantic import BaseModel, field_serializer


class PlayStyle(str, Enum):
    MOUSE = "mouse"
    KEYBOARD = "keyboard"
    TABLET = "tablet"
    TOUCH = "touch"


class Country(BaseModel):
    code: str
    name: str


class Cover(BaseModel):
    custom_url: str | None = None
    url: str | None = None
    id: int | None = None


class Level(BaseModel):
    current: int
    progress: int


class GradeCounts(BaseModel):
    ss: int = 0
    ssh: int = 0
    s: int = 0
    sh: int = 0
    a: int = 0


class Rank(BaseModel):
    country: int | None = None


class Statistics(BaseModel):
    count_100: int = 0
    count_300: int = 0
    count_50: int = 0
    count_miss: int = 0
    level: Level
    global_rank: int | None = None
    global_rank_exp: int | None = None
    pp: float = 0.0
    pp_exp: float = 0.0
    ranked_score: int = 0
    hit_accuracy: float = 0.0
    play_count: int = 0
    play_time: int = 0
    total_score: int = 0
    total_hits: int = 0
    maximum_combo: int = 0
    replays_watched_by_others: int = 0
    is_ranked: bool = False
    grade_counts: GradeCounts
    rank: Rank


class Kudosu(BaseModel):
    available: int = 0
    total: int = 0


class MonthlyPlaycount(BaseModel):
    start_date: str
    count: int


class UserAchievement(BaseModel):
    achieved_at: datetime
    achievement_id: int

    # 添加数据库模型转换方法
    def to_db_model(self, user_id: int) -> LazerUserAchievement:
        return LazerUserAchievement(
            user_id=user_id,
            achievement_id=self.achievement_id,
            achieved_at=self.achieved_at,
        )


class RankHighest(BaseModel):
    rank: int
    updated_at: datetime

    @field_serializer('updated_at')
    def serialize_updated_at(self, dt: datetime) -> str:
        """序列化updated_at为带时区的ISO字符串"""
        if dt.tzinfo is None:
            from datetime import UTC
            dt = dt.replace(tzinfo=UTC)
        return dt.isoformat().replace('+00:00', '+00:00')


class RankHistory(BaseModel):
    mode: str
    data: list[int]


class DailyChallengeStats(BaseModel):
    daily_streak_best: int = 0
    daily_streak_current: int = 0
    last_update: datetime
    last_weekly_streak: datetime
    playcount: int = 0
    top_10p_placements: int = 0
    top_50p_placements: int = 0
    user_id: int
    weekly_streak_best: int = 0
    weekly_streak_current: int = 0

    @field_serializer('last_update', 'last_weekly_streak')
    def serialize_datetime(self, dt: datetime) -> str:
        """序列化datetime为带时区的ISO字符串"""
        if dt.tzinfo is None:
            from datetime import UTC
            dt = dt.replace(tzinfo=UTC)
        return dt.isoformat().replace('+00:00', '+00:00')


class Page(BaseModel):
    html: str = ""
    raw: str = ""


class User(BaseModel):
    # 基本信息 - 匹配 JSON 格式
    avatar_url: str
    country_code: str
    default_group: str = "default"
    id: int
    is_active: bool = True
    is_bot: bool = False
    is_deleted: bool = False
    is_online: bool = True
    is_supporter: bool = False
    last_visit: datetime | None = None
    pm_friends_only: bool = False
    profile_colour: str | None = None
    username: str

    # 个人资料信息
    cover_url: str | None = None
    discord: str | None = None
    has_supported: bool = False
    interests: str | None = None
    join_date: datetime
    location: str | None = None
    max_blocks: int = 50  # 修改默认值为50，匹配官方API
    max_friends: int = 250  # 修改默认值为250，匹配官方API
    occupation: str | None = None
    playmode: str = "osu"
    playstyle: list[str] | None = None
    post_count: int = 0
    profile_hue: int | None = None
    profile_order: list[str] = [
        "me",
        "recent_activity",
        "top_ranks",
        "medals",
        "historical",
        "beatmaps",
        "kudosu",
    ]
    title: str | None = None
    title_url: str | None = None
    twitter: str | None = None
    website: str | None = None

    # 关联对象
    country: Country
    cover: Cover
    is_restricted: bool = False
    kudosu: Kudosu

    # 历史和计数信息
    account_history: list[dict] = []
    active_tournament_banner: dict | None = None
    active_tournament_banners: list[dict] = []
    badges: list[dict] = []
    beatmap_playcounts_count: int = 0
    comments_count: int = 0
    current_season_stats: dict | None = None
    daily_challenge_user_stats: DailyChallengeStats
    favourite_beatmapset_count: int = 0
    follower_count: int = 0
    graveyard_beatmapset_count: int = 0
    groups: list[dict] = []
    guest_beatmapset_count: int = 0
    loved_beatmapset_count: int = 0
    mapping_follower_count: int = 0
    monthly_playcounts: list[dict] = []
    nominated_beatmapset_count: int = 0
    page: Page = Page()
    pending_beatmapset_count: int = 0
    previous_usernames: list[str] = []
    rank_highest: RankHighest | None = None
    ranked_beatmapset_count: int = 0
    replays_watched_counts: list[dict] = []
    scores_best_count: int = 0
    scores_first_count: int = 0
    scores_pinned_count: int = 0
    scores_recent_count: int = 0
    session_verified: bool = True
    statistics: Statistics
    statistics_rulesets: dict[str, Statistics] | None = None
    support_level: int = 0
    team: Team | None = None
    user_achievements: list[dict] = []
    rank_history: list[int] | None = None
    rankHistory: list[int] | None = None  # 兼容性别名
    ranked_and_approved_beatmapset_count: int = 0
    unranked_beatmapset_count: int = 0

    @field_serializer('last_visit', 'join_date')
    def serialize_datetime(self, dt: datetime | None) -> str | None:
        """序列化datetime为带时区的ISO字符串"""
        if dt is None:
            return None
        if dt.tzinfo is None:
            from datetime import UTC
            dt = dt.replace(tzinfo=UTC)
        return dt.isoformat().replace('+00:00', '+00:00')


class APIMe(User):
    """APIMe class that extends User to match osu client expectations for /me endpoint"""
    session_verified: bool = True
