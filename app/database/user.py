from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from .legacy import LegacyUserStatistics
from .team import TeamMember

from sqlalchemy import DECIMAL, JSON, Column, Date, DateTime, Text
from sqlalchemy.dialects.mysql import VARCHAR
from sqlmodel import BigInteger, Field, Relationship, SQLModel


class User(SQLModel, table=True):
    __tablename__ = "users"  # pyright: ignore[reportAssignmentType]

    # 主键
    id: int = Field(default=None, primary_key=True, index=True, nullable=False)

    # 基本信息（匹配 migrations 中的结构）
    name: str = Field(max_length=32, unique=True, index=True)  # 用户名
    safe_name: str = Field(max_length=32, unique=True, index=True)  # 安全用户名
    email: str = Field(max_length=254, unique=True, index=True)
    priv: int = Field(default=1)  # 权限
    pw_bcrypt: str = Field(max_length=60)  # bcrypt 哈希密码
    country: str = Field(default="CN", max_length=2)  # 国家代码

    # 状态和时间
    silence_end: int = Field(default=0)
    donor_end: int = Field(default=0)
    creation_time: int = Field(default=0)  # Unix 时间戳
    latest_activity: int = Field(default=0)  # Unix 时间戳

    # 游戏相关
    preferred_mode: int = Field(default=0)  # 偏好游戏模式
    play_style: int = Field(default=0)  # 游戏风格

    # 扩展信息
    clan_id: int = Field(default=0)
    clan_priv: int = Field(default=0)
    custom_badge_name: str | None = Field(default=None, max_length=16)
    custom_badge_icon: str | None = Field(default=None, max_length=64)
    userpage_content: str | None = Field(default=None, max_length=2048)
    api_key: str | None = Field(default=None, max_length=36, unique=True)

    # 虚拟字段用于兼容性
    @property
    def username(self):
        return self.name

    @property
    def country_code(self):
        return self.country

    @property
    def join_date(self):
        creation_time = getattr(self, "creation_time", 0)
        return (
            datetime.fromtimestamp(creation_time)
            if creation_time > 0
            else datetime.utcnow()
        )

    @property
    def last_visit(self):
        latest_activity = getattr(self, "latest_activity", 0)
        return datetime.fromtimestamp(latest_activity) if latest_activity > 0 else None

    # 关联关系
    lazer_profile: Optional["LazerUserProfile"] = Relationship(back_populates="user")
    lazer_statistics: list["LazerUserStatistics"] = Relationship(back_populates="user")
    lazer_counts: Optional["LazerUserCounts"] = Relationship(back_populates="user")
    lazer_achievements: list["LazerUserAchievement"] = Relationship(
        back_populates="user"
    )
    lazer_profile_sections: list["LazerUserProfileSections"] = Relationship(
        back_populates="user"
    )
    statistics: list["LegacyUserStatistics"] = Relationship(back_populates="user")
    team_membership: list["TeamMember"] = Relationship(back_populates="user")
    daily_challenge_stats: Optional["DailyChallengeStats"] = Relationship(
        back_populates="user"
    )
    rank_history: list["RankHistory"] = Relationship(back_populates="user")
    avatar: Optional["UserAvatar"] = Relationship(back_populates="user")
    active_banners: list["LazerUserBanners"] = Relationship(back_populates="user")
    lazer_badges: list["LazerUserBadge"] = Relationship(back_populates="user")
    lazer_monthly_playcounts: list["LazerUserMonthlyPlaycounts"] = Relationship(
        back_populates="user"
    )
    lazer_previous_usernames: list["LazerUserPreviousUsername"] = Relationship(
        back_populates="user"
    )
    lazer_replays_watched: list["LazerUserReplaysWatched"] = Relationship(
        back_populates="user"
    )


# ============================================
# Lazer API 专用表模型
# ============================================


class LazerUserProfile(SQLModel, table=True):
    __tablename__ = "lazer_user_profiles"  # pyright: ignore[reportAssignmentType]

    user_id: int = Field(foreign_key="users.id", primary_key=True)

    # 基本状态字段
    is_active: bool = Field(default=True)
    is_bot: bool = Field(default=False)
    is_deleted: bool = Field(default=False)
    is_online: bool = Field(default=True)
    is_supporter: bool = Field(default=False)
    is_restricted: bool = Field(default=False)
    session_verified: bool = Field(default=False)
    has_supported: bool = Field(default=False)
    pm_friends_only: bool = Field(default=False)

    # 基本资料字段
    default_group: str = Field(default="default", max_length=50)
    last_visit: datetime | None = Field(default=None, sa_column=Column(DateTime))
    join_date: datetime | None = Field(default=None, sa_column=Column(DateTime))
    profile_colour: str | None = Field(default=None, max_length=7)
    profile_hue: int | None = Field(default=None)

    # 社交媒体和个人资料字段
    avatar_url: str | None = Field(default=None, max_length=500)
    cover_url: str | None = Field(default=None, max_length=500)
    discord: str | None = Field(default=None, max_length=100)
    twitter: str | None = Field(default=None, max_length=100)
    website: str | None = Field(default=None, max_length=500)
    title: str | None = Field(default=None, max_length=100)
    title_url: str | None = Field(default=None, max_length=500)
    interests: str | None = Field(default=None, sa_column=Column(Text))
    location: str | None = Field(default=None, max_length=100)

    occupation: str | None = Field(default=None)  # 职业字段，默认为 None

    # 游戏相关字段
    playmode: str = Field(default="osu", max_length=10)
    support_level: int = Field(default=0)
    max_blocks: int = Field(default=50)  # 修改默认值为50，匹配官方API
    max_friends: int = Field(default=250)  # 修改默认值为250，匹配官方API
    post_count: int = Field(default=0)

    # 页面内容
    page_html: str | None = Field(default=None, sa_column=Column(Text))
    page_raw: str | None = Field(default=None, sa_column=Column(Text))

    profile_order: str = Field(
        default="me,recent_activity,top_ranks,medals,historical,beatmaps,kudosu"
    )

    # 关联关系
    user: "User" = Relationship(back_populates="lazer_profile")


class LazerUserProfileSections(SQLModel, table=True):
    __tablename__ = "lazer_user_profile_sections"  # pyright: ignore[reportAssignmentType]

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    section_name: str = Field(sa_column=Column(VARCHAR(50)))
    display_order: int | None = Field(default=None)

    created_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column=Column(DateTime)
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column=Column(DateTime)
    )

    user: "User" = Relationship(back_populates="lazer_profile_sections")


class LazerUserCountry(SQLModel, table=True):
    __tablename__ = "lazer_user_countries"  # pyright: ignore[reportAssignmentType]

    user_id: int = Field(foreign_key="users.id", primary_key=True)
    code: str = Field(max_length=2)
    name: str = Field(max_length=100)

    created_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column=Column(DateTime)
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column=Column(DateTime)
    )


class LazerUserKudosu(SQLModel, table=True):
    __tablename__ = "lazer_user_kudosu"  # pyright: ignore[reportAssignmentType]

    user_id: int = Field(foreign_key="users.id", primary_key=True)
    available: int = Field(default=0)
    total: int = Field(default=0)

    created_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column=Column(DateTime)
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column=Column(DateTime)
    )


class LazerUserCounts(SQLModel, table=True):
    __tablename__ = "lazer_user_counts"  # pyright: ignore[reportAssignmentType]

    user_id: int = Field(foreign_key="users.id", primary_key=True)

    # 统计计数字段
    beatmap_playcounts_count: int = Field(default=0)
    comments_count: int = Field(default=0)
    favourite_beatmapset_count: int = Field(default=0)
    follower_count: int = Field(default=0)
    graveyard_beatmapset_count: int = Field(default=0)
    guest_beatmapset_count: int = Field(default=0)
    loved_beatmapset_count: int = Field(default=0)
    mapping_follower_count: int = Field(default=0)
    nominated_beatmapset_count: int = Field(default=0)
    pending_beatmapset_count: int = Field(default=0)
    ranked_beatmapset_count: int = Field(default=0)
    ranked_and_approved_beatmapset_count: int = Field(default=0)
    unranked_beatmapset_count: int = Field(default=0)
    scores_best_count: int = Field(default=0)
    scores_first_count: int = Field(default=0)
    scores_pinned_count: int = Field(default=0)
    scores_recent_count: int = Field(default=0)

    created_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column=Column(DateTime)
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column=Column(DateTime)
    )

    # 关联关系
    user: "User" = Relationship(back_populates="lazer_counts")


class LazerUserStatistics(SQLModel, table=True):
    __tablename__ = "lazer_user_statistics"  # pyright: ignore[reportAssignmentType]

    user_id: int = Field(foreign_key="users.id", primary_key=True)
    mode: str = Field(default="osu", max_length=10, primary_key=True)

    # 基本命中统计
    count_100: int = Field(default=0)
    count_300: int = Field(default=0)
    count_50: int = Field(default=0)
    count_miss: int = Field(default=0)

    # 等级信息
    level_current: int = Field(default=1)
    level_progress: int = Field(default=0)

    # 排名信息
    global_rank: int | None = Field(default=None)
    global_rank_exp: int | None = Field(default=None)
    country_rank: int | None = Field(default=None)

    # PP 和分数
    pp: float = Field(default=0.00, sa_column=Column(DECIMAL(10, 2)))
    pp_exp: float = Field(default=0.00, sa_column=Column(DECIMAL(10, 2)))
    ranked_score: int = Field(default=0, sa_column=Column(BigInteger))
    hit_accuracy: float = Field(default=0.00, sa_column=Column(DECIMAL(5, 2)))
    total_score: int = Field(default=0, sa_column=Column(BigInteger))
    total_hits: int = Field(default=0, sa_column=Column(BigInteger))
    maximum_combo: int = Field(default=0)

    # 游戏统计
    play_count: int = Field(default=0)
    play_time: int = Field(default=0)  # 秒
    replays_watched_by_others: int = Field(default=0)
    is_ranked: bool = Field(default=False)

    # 成绩等级计数
    grade_ss: int = Field(default=0)
    grade_ssh: int = Field(default=0)
    grade_s: int = Field(default=0)
    grade_sh: int = Field(default=0)
    grade_a: int = Field(default=0)

    # 最高排名记录
    rank_highest: int | None = Field(default=None)
    rank_highest_updated_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime)
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column=Column(DateTime)
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column=Column(DateTime)
    )

    # 关联关系
    user: "User" = Relationship(back_populates="lazer_statistics")


class LazerUserBanners(SQLModel, table=True):
    __tablename__ = "lazer_user_tournament_banners"  # pyright: ignore[reportAssignmentType]

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    tournament_id: int
    image_url: str = Field(sa_column=Column(VARCHAR(500)))
    is_active: bool | None = Field(default=None)

    # 修正user关系的back_populates值
    user: "User" = Relationship(back_populates="active_banners")


class LazerUserAchievement(SQLModel, table=True):
    __tablename__ = "lazer_user_achievements"  # pyright: ignore[reportAssignmentType]

    id: int | None = Field(default=None, primary_key=True, index=True)
    user_id: int = Field(foreign_key="users.id")
    achievement_id: int
    achieved_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column=Column(DateTime)
    )

    user: "User" = Relationship(back_populates="lazer_achievements")


class LazerUserBadge(SQLModel, table=True):
    __tablename__ = "lazer_user_badges"  # pyright: ignore[reportAssignmentType]

    id: int | None = Field(default=None, primary_key=True, index=True)
    user_id: int = Field(foreign_key="users.id")
    badge_id: int
    awarded_at: datetime | None = Field(default=None, sa_column=Column(DateTime))
    description: str | None = Field(default=None, sa_column=Column(Text))
    image_url: str | None = Field(default=None, max_length=500)
    url: str | None = Field(default=None, max_length=500)

    created_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column=Column(DateTime)
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column=Column(DateTime)
    )

    user: "User" = Relationship(back_populates="lazer_badges")


class LazerUserMonthlyPlaycounts(SQLModel, table=True):
    __tablename__ = "lazer_user_monthly_playcounts"  # pyright: ignore[reportAssignmentType]

    id: int | None = Field(default=None, primary_key=True, index=True)
    user_id: int = Field(foreign_key="users.id")
    start_date: datetime = Field(sa_column=Column(Date))
    play_count: int = Field(default=0)

    created_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column=Column(DateTime)
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column=Column(DateTime)
    )

    user: "User" = Relationship(back_populates="lazer_monthly_playcounts")


class LazerUserPreviousUsername(SQLModel, table=True):
    __tablename__ = "lazer_user_previous_usernames"  # pyright: ignore[reportAssignmentType]

    id: int | None = Field(default=None, primary_key=True, index=True)
    user_id: int = Field(foreign_key="users.id")
    username: str = Field(max_length=32)
    changed_at: datetime = Field(sa_column=Column(DateTime))

    created_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column=Column(DateTime)
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column=Column(DateTime)
    )

    user: "User" = Relationship(back_populates="lazer_previous_usernames")


class LazerUserReplaysWatched(SQLModel, table=True):
    __tablename__ = "lazer_user_replays_watched"  # pyright: ignore[reportAssignmentType]

    id: int | None = Field(default=None, primary_key=True, index=True)
    user_id: int = Field(foreign_key="users.id")
    start_date: datetime = Field(sa_column=Column(Date))
    count: int = Field(default=0)

    created_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column=Column(DateTime)
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column=Column(DateTime)
    )

    user: "User" = Relationship(back_populates="lazer_replays_watched")


# 类型转换用的 UserAchievement（不是 SQLAlchemy 模型）
@dataclass
class UserAchievement:
    achieved_at: datetime
    achievement_id: int


class DailyChallengeStats(SQLModel, table=True):
    __tablename__ = "daily_challenge_stats"  # pyright: ignore[reportAssignmentType]

    id: int | None = Field(default=None, primary_key=True, index=True)
    user_id: int = Field(foreign_key="users.id", unique=True)

    daily_streak_best: int = Field(default=0)
    daily_streak_current: int = Field(default=0)
    last_update: datetime | None = Field(default=None, sa_column=Column(DateTime))
    last_weekly_streak: datetime | None = Field(
        default=None, sa_column=Column(DateTime)
    )
    playcount: int = Field(default=0)
    top_10p_placements: int = Field(default=0)
    top_50p_placements: int = Field(default=0)
    weekly_streak_best: int = Field(default=0)
    weekly_streak_current: int = Field(default=0)

    user: "User" = Relationship(back_populates="daily_challenge_stats")


class RankHistory(SQLModel, table=True):
    __tablename__ = "rank_history"  # pyright: ignore[reportAssignmentType]

    id: int | None = Field(default=None, primary_key=True, index=True)
    user_id: int = Field(foreign_key="users.id")
    mode: str = Field(max_length=10)
    rank_data: list = Field(sa_column=Column(JSON))  # Array of ranks
    date_recorded: datetime = Field(
        default_factory=datetime.utcnow, sa_column=Column(DateTime)
    )

    user: "User" = Relationship(back_populates="rank_history")


class UserAvatar(SQLModel, table=True):
    __tablename__ = "user_avatars"  # pyright: ignore[reportAssignmentType]

    id: int | None = Field(default=None, primary_key=True, index=True)
    user_id: int = Field(foreign_key="users.id")
    filename: str = Field(max_length=255)
    original_filename: str = Field(max_length=255)
    file_size: int
    mime_type: str = Field(max_length=100)
    is_active: bool = Field(default=True)
    created_at: int = Field(default_factory=lambda: int(datetime.now().timestamp()))
    updated_at: int = Field(default_factory=lambda: int(datetime.now().timestamp()))
    r2_original_url: str | None = Field(default=None, max_length=500)
    r2_game_url: str | None = Field(default=None, max_length=500)

    user: "User" = Relationship(back_populates="avatar")
