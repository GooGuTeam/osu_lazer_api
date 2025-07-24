from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import (
    DECIMAL,
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.mysql import TINYINT, VARCHAR
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    # 主键
    id = Column(Integer, primary_key=True, index=True)

    # 基本信息（匹配 migrations 中的结构）
    name = Column(String(32), unique=True, index=True, nullable=False)  # 用户名
    safe_name = Column(
        String(32), unique=True, index=True, nullable=False
    )  # 安全用户名
    email = Column(String(254), unique=True, index=True, nullable=False)
    priv = Column(Integer, default=1, nullable=False)  # 权限
    pw_bcrypt = Column(String(60), nullable=False)  # bcrypt 哈希密码
    country = Column(String(2), default="CN", nullable=False)  # 国家代码

    # 状态和时间
    silence_end = Column(Integer, default=0, nullable=False)
    donor_end = Column(Integer, default=0, nullable=False)
    creation_time = Column(Integer, default=0, nullable=False)  # Unix 时间戳
    latest_activity = Column(Integer, default=0, nullable=False)  # Unix 时间戳

    # 游戏相关
    preferred_mode = Column(Integer, default=0, nullable=False)  # 偏好游戏模式
    play_style = Column(Integer, default=0, nullable=False)  # 游戏风格

    # 扩展信息
    clan_id = Column(Integer, default=0, nullable=False)
    clan_priv = Column(Integer, default=0, nullable=False)
    custom_badge_name = Column(String(16))
    custom_badge_icon = Column(String(64))
    userpage_content = Column(String(2048))
    api_key = Column(String(36), unique=True)

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
    lazer_profile = relationship(
        "LazerUserProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    lazer_statistics = relationship(
        "LazerUserStatistics", back_populates="user", cascade="all, delete-orphan"
    )
    lazer_achievements = relationship(
        "LazerUserAchievement", back_populates="user", cascade="all, delete-orphan"
    )
    lazer_profile_sections = relationship(
        "LazerUserProfileSections",  # 修正类名拼写（添加s）
        back_populates="user",
        cascade="all, delete-orphan",
    )
    statistics = relationship(
        "LegacyUserStatistics", back_populates="user", cascade="all, delete-orphan"
    )
    achievements = relationship(
        "LazerUserAchievement",
        back_populates="user",
        cascade="all, delete-orphan",
        overlaps="lazer_achievements",
    )
    team_membership = relationship(
        "TeamMember", back_populates="user", cascade="all, delete-orphan"
    )
    daily_challenge_stats = relationship(
        "DailyChallengeStats",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    rank_history = relationship(
        "RankHistory", back_populates="user", cascade="all, delete-orphan"
    )
    avatar = relationship(
        "UserAvatar",
        back_populates="user",
        primaryjoin="and_(User.id==UserAvatar.user_id, UserAvatar.is_active==True)",
        uselist=False,
    )
    active_banners = relationship(
        "LazerUserBanners",  # 原定义指向LazerUserBanners，实际应为UserAvatar
        back_populates="user",
        primaryjoin=(
            "and_(User.id==LazerUserBanners.user_id, LazerUserBanners.is_active==True)"
        ),
        uselist=False,
    )
    lazer_badges = relationship(
        "LazerUserBadge", back_populates="user", cascade="all, delete-orphan"
    )
    lazer_monthly_playcounts = relationship(
        "LazerUserMonthlyPlaycounts",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    lazer_previous_usernames = relationship(
        "LazerUserPreviousUsername", back_populates="user", cascade="all, delete-orphan"
    )
    lazer_replays_watched = relationship(
        "LazerUserReplaysWatched", back_populates="user", cascade="all, delete-orphan"
    )
    


# ============================================
# Lazer API 专用表模型
# ============================================


class LazerUserProfile(Base):
    __tablename__ = "lazer_user_profiles"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)

    # 基本状态字段
    is_active = Column(Boolean, default=True)
    is_bot = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)
    is_online = Column(Boolean, default=True)
    is_supporter = Column(Boolean, default=False)
    is_restricted = Column(Boolean, default=False)
    session_verified = Column(Boolean, default=False)
    has_supported = Column(Boolean, default=False)
    pm_friends_only = Column(Boolean, default=False)

    # 基本资料字段
    default_group = Column(String(50), default="default")
    last_visit = Column(DateTime)
    join_date = Column(DateTime)
    profile_colour = Column(String(7))
    profile_hue = Column(Integer)

    # 社交媒体和个人资料字段
    avatar_url = Column(String(500))
    cover_url = Column(String(500))
    discord = Column(String(100))
    twitter = Column(String(100))
    website = Column(String(500))
    title = Column(String(100))
    title_url = Column(String(500))
    interests = Column(Text)
    location = Column(String(100))

    occupation = None  # 职业字段，默认为 None

    # 游戏相关字段
    playmode = Column(String(10), default="osu")
    support_level = Column(Integer, default=0)
    max_blocks = Column(Integer, default=100)
    max_friends = Column(Integer, default=500)
    post_count = Column(Integer, default=0)

    # 页面内容
    page_html = Column(Text)
    page_raw = Column(Text)

    # created_at = Column(DateTime, default=datetime.utcnow)
    # updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联关系
    user = relationship("User", back_populates="lazer_profile")


class LazerUserProfileSections(Base):
    __tablename__ = "lazer_user_profile_sections"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    section_name = Column(VARCHAR(50), nullable=False)
    display_order = Column(Integer)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="lazer_profile_sections")


class LazerUserCountry(Base):
    __tablename__ = "lazer_user_countries"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    code = Column(String(2), nullable=False)
    name = Column(String(100), nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class LazerUserKudosu(Base):
    __tablename__ = "lazer_user_kudosu"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    available = Column(Integer, default=0)
    total = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class LazerUserCounts(Base):
    __tablename__ = "lazer_user_counts"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)

    # 统计计数字段
    beatmap_playcounts_count = Column(Integer, default=0)
    comments_count = Column(Integer, default=0)
    favourite_beatmapset_count = Column(Integer, default=0)
    follower_count = Column(Integer, default=0)
    graveyard_beatmapset_count = Column(Integer, default=0)
    guest_beatmapset_count = Column(Integer, default=0)
    loved_beatmapset_count = Column(Integer, default=0)
    mapping_follower_count = Column(Integer, default=0)
    nominated_beatmapset_count = Column(Integer, default=0)
    pending_beatmapset_count = Column(Integer, default=0)
    ranked_beatmapset_count = Column(Integer, default=0)
    ranked_and_approved_beatmapset_count = Column(Integer, default=0)
    unranked_beatmapset_count = Column(Integer, default=0)
    scores_best_count = Column(Integer, default=0)
    scores_first_count = Column(Integer, default=0)
    scores_pinned_count = Column(Integer, default=0)
    scores_recent_count = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class LazerUserStatistics(Base):
    __tablename__ = "lazer_user_statistics"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    mode = Column(String(10), nullable=False, default="osu", primary_key=True)

    # 基本命中统计
    count_100 = Column(Integer, default=0)
    count_300 = Column(Integer, default=0)
    count_50 = Column(Integer, default=0)
    count_miss = Column(Integer, default=0)

    # 等级信息
    level_current = Column(Integer, default=1)
    level_progress = Column(Integer, default=0)

    # 排名信息
    global_rank = Column(Integer)
    global_rank_exp = Column(Integer)
    country_rank = Column(Integer)

    # PP 和分数
    pp = Column(DECIMAL(10, 2), default=0.00)
    pp_exp = Column(DECIMAL(10, 2), default=0.00)
    ranked_score = Column(Integer, default=0)
    hit_accuracy = Column(DECIMAL(5, 2), default=0.00)
    total_score = Column(Integer, default=0)
    total_hits = Column(Integer, default=0)
    maximum_combo = Column(Integer, default=0)

    # 游戏统计
    play_count = Column(Integer, default=0)
    play_time = Column(Integer, default=0)  # 秒
    replays_watched_by_others = Column(Integer, default=0)
    is_ranked = Column(Boolean, default=False)

    # 成绩等级计数
    grade_ss = Column(Integer, default=0)
    grade_ssh = Column(Integer, default=0)
    grade_s = Column(Integer, default=0)
    grade_sh = Column(Integer, default=0)
    grade_a = Column(Integer, default=0)

    # 最高排名记录
    rank_highest = Column(Integer)
    rank_highest_updated_at = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联关系
    user = relationship("User", back_populates="lazer_statistics")


class LazerUserBanners(Base):
    __tablename__ = "lazer_user_tournament_banners"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    tournament_id = Column(Integer, nullable=False)
    image_url = Column(VARCHAR(500), nullable=False)
    is_active = Column(TINYINT(1))

    # 修正user关系的back_populates值
    user = relationship(
        "User",
        back_populates="active_banners",  # 改为实际存在的属性名
    )


class LazerUserAchievement(Base):
    __tablename__ = "lazer_user_achievements"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    achievement_id = Column(Integer, nullable=False)
    achieved_at = Column(DateTime, default=datetime.utcnow)

    # created_at = Column(DateTime, default=datetime.utcnow)
    # updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="lazer_achievements")


class LazerUserBadge(Base):
    __tablename__ = "lazer_user_badges"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    badge_id = Column(Integer, nullable=False)
    awarded_at = Column(DateTime)
    description = Column(Text)
    image_url = Column(String(500))
    url = Column(String(500))

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="lazer_badges")


class LazerUserMonthlyPlaycounts(Base):
    __tablename__ = "lazer_user_monthly_playcounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    start_date = Column(Date, nullable=False)
    play_count = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="lazer_monthly_playcounts")


class LazerUserPreviousUsername(Base):
    __tablename__ = "lazer_user_previous_usernames"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    username = Column(String(32), nullable=False)
    changed_at = Column(DateTime, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="lazer_previous_usernames")


class LazerUserReplaysWatched(Base):
    __tablename__ = "lazer_user_replays_watched"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    start_date = Column(Date, nullable=False)
    count = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="lazer_replays_watched")


# ============================================
# 旧的兼容性表模型（保留以便向后兼容）
# ============================================


class LegacyUserStatistics(Base):
    __tablename__ = "user_statistics"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    mode = Column(String(10), nullable=False)  # osu, taiko, fruits, mania

    # 基本统计
    count_100 = Column(Integer, default=0)
    count_300 = Column(Integer, default=0)
    count_50 = Column(Integer, default=0)
    count_miss = Column(Integer, default=0)

    # 等级信息
    level_current = Column(Integer, default=1)
    level_progress = Column(Integer, default=0)

    # 排名信息
    global_rank = Column(Integer)
    global_rank_exp = Column(Integer)
    country_rank = Column(Integer)

    # PP 和分数
    pp = Column(Float, default=0.0)
    pp_exp = Column(Float, default=0.0)
    ranked_score = Column(Integer, default=0)
    hit_accuracy = Column(Float, default=0.0)
    total_score = Column(Integer, default=0)
    total_hits = Column(Integer, default=0)
    maximum_combo = Column(Integer, default=0)

    # 游戏统计
    play_count = Column(Integer, default=0)
    play_time = Column(Integer, default=0)
    replays_watched_by_others = Column(Integer, default=0)
    is_ranked = Column(Boolean, default=False)

    # 成绩等级计数
    grade_ss = Column(Integer, default=0)
    grade_ssh = Column(Integer, default=0)
    grade_s = Column(Integer, default=0)
    grade_sh = Column(Integer, default=0)
    grade_a = Column(Integer, default=0)

    # 最高排名记录
    rank_highest = Column(Integer)
    rank_highest_updated_at = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联关系
    user = relationship("User", back_populates="statistics")


class LegacyOAuthToken(Base):
    __tablename__ = "legacy_oauth_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    access_token = Column(String(255), nullable=False, index=True)
    refresh_token = Column(String(255), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    previous_usernames = Column(JSON, default=list)
    replays_watched_counts = Column(JSON, default=list)

    # 用户关系
    user = relationship("User")


# class UserAchievement(Base):
#     __tablename__ = "lazer_user_achievements"

#     id = Column(Integer, primary_key=True, index=True)
#     user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
#     achievement_id = Column(Integer, nullable=False)
#     achieved_at = Column(DateTime, default=datetime.utcnow)

#     user = relationship("User", back_populates="achievements")


# 类型转换用的 UserAchievement（不是 SQLAlchemy 模型）
@dataclass
class UserAchievement:
    achieved_at: datetime
    achievement_id: int


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    short_name = Column(String(10), nullable=False)
    flag_url = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)

    members = relationship(
        "TeamMember", back_populates="team", cascade="all, delete-orphan"
    )


class TeamMember(Base):
    __tablename__ = "team_members"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    joined_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="team_membership")
    team = relationship("Team", back_populates="members")


class DailyChallengeStats(Base):
    __tablename__ = "daily_challenge_stats"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)

    daily_streak_best = Column(Integer, default=0)
    daily_streak_current = Column(Integer, default=0)
    last_update = Column(DateTime)
    last_weekly_streak = Column(DateTime)
    playcount = Column(Integer, default=0)
    top_10p_placements = Column(Integer, default=0)
    top_50p_placements = Column(Integer, default=0)
    weekly_streak_best = Column(Integer, default=0)
    weekly_streak_current = Column(Integer, default=0)

    user = relationship("User", back_populates="daily_challenge_stats")


class RankHistory(Base):
    __tablename__ = "rank_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    mode = Column(String(10), nullable=False)
    rank_data = Column(JSON, nullable=False)  # Array of ranks
    date_recorded = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="rank_history")


class OAuthToken(Base):
    __tablename__ = "oauth_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    access_token = Column(String(500), unique=True, nullable=False)
    refresh_token = Column(String(500), unique=True, nullable=False)
    token_type = Column(String(20), default="Bearer")
    scope = Column(String(100), default="*")
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")


class UserAvatar(Base):
    __tablename__ = "user_avatars"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(Integer, default=lambda: int(datetime.now().timestamp()))
    updated_at = Column(Integer, default=lambda: int(datetime.now().timestamp()))
    r2_original_url = Column(String(500))
    r2_game_url = Column(String(500))

    user = relationship("User", back_populates="avatar")
