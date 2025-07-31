from datetime import UTC, datetime
from typing import TYPE_CHECKING, NotRequired, TypedDict

from app.models.model import UTCBaseModel
from app.models.score import GameMode
from app.models.user import Country, Page, RankHistory

from .achievement import UserAchievement, UserAchievementResp
from .daily_challenge import DailyChallengeStats, DailyChallengeStatsResp
from .monthly_playcounts import MonthlyPlaycounts, MonthlyPlaycountsResp
from .statistics import UserStatistics, UserStatisticsResp
from .team import Team, TeamMember
from .user_account_history import UserAccountHistory, UserAccountHistoryResp

from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlmodel import (
    JSON,
    BigInteger,
    Column,
    DateTime,
    Field,
    Relationship,
    SQLModel,
    func,
    select,
)
from sqlmodel.ext.asyncio.session import AsyncSession

if TYPE_CHECKING:
    from app.database.relationship import RelationshipResp


class Kudosu(TypedDict):
    available: int
    total: int


class RankHighest(TypedDict):
    rank: int
    updated_at: datetime


class UserProfileCover(TypedDict):
    url: str
    custom_url: NotRequired[str]
    id: NotRequired[str]


Badge = TypedDict(
    "Badge",
    {
        "awarded_at": datetime,
        "description": str,
        "image@2x_url": str,
        "image_url": str,
        "url": str,
    },
)


class UserBase(UTCBaseModel, SQLModel):
    avatar_url: str = ""
    country_code: str = Field(default="CN", max_length=2, index=True)
    # ? default_group: str|None
    is_active: bool = True
    is_bot: bool = False
    is_supporter: bool = False
    last_visit: datetime = Field(
        default=datetime.now(UTC), sa_column=Column(DateTime(timezone=True))
    )
    pm_friends_only: bool = False
    profile_colour: str | None = None
    username: str = Field(max_length=32, unique=True, index=True)
    page: Page = Field(sa_column=Column(JSON), default=Page(html="", raw=""))
    previous_usernames: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    # TODO: replays_watched_counts
    support_level: int = 0
    badges: list[Badge] = Field(default_factory=list, sa_column=Column(JSON))

    # optional
    is_restricted: bool = False
    # blocks
    cover: UserProfileCover = Field(
        default=UserProfileCover(
            url="https://assets.ppy.sh/user-profile-covers/default.jpeg"
        ),
        sa_column=Column(JSON),
    )
    beatmap_playcounts_count: int = 0
    # kudosu

    # UserExtended
    playmode: GameMode = GameMode.OSU
    discord: str | None = None
    has_supported: bool = False
    interests: str | None = None
    join_date: datetime = Field(default=datetime.now(UTC))
    location: str | None = None
    max_blocks: int = 50
    max_friends: int = 500
    occupation: str | None = None
    playstyle: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    # TODO: post_count
    profile_hue: int | None = None
    profile_order: list[str] = Field(
        default_factory=lambda: [
            "me",
            "recent_activity",
            "top_ranks",
            "medals",
            "historical",
            "beatmaps",
            "kudosu",
        ],
        sa_column=Column(JSON),
    )
    title: str | None = None
    title_url: str | None = None
    twitter: str | None = None
    website: str | None = None

    # undocumented
    comments_count: int = 0
    post_count: int = 0
    is_admin: bool = False
    is_gmt: bool = False
    is_qat: bool = False
    is_bng: bool = False


class User(AsyncAttrs, UserBase, table=True):
    __tablename__ = "lazer_users"  # pyright: ignore[reportAssignmentType]

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True, index=True),
    )
    account_history: list[UserAccountHistory] = Relationship()
    statistics: list[UserStatistics] = Relationship()
    achievement: list[UserAchievement] = Relationship(back_populates="user")
    team_membership: TeamMember | None = Relationship(back_populates="user")
    daily_challenge_stats: DailyChallengeStats | None = Relationship(
        back_populates="user"
    )
    monthly_playcounts: list[MonthlyPlaycounts] = Relationship(back_populates="user")

    email: str = Field(max_length=254, unique=True, index=True, exclude=True)
    priv: int = Field(default=1, exclude=True)
    pw_bcrypt: str = Field(max_length=60, exclude=True)
    silence_end_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True)), exclude=True
    )
    donor_end_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True)), exclude=True
    )


class UserResp(UserBase):
    id: int | None = None
    is_online: bool = True  # TODO
    groups: list = []  # TODO
    country: Country = Field(default_factory=lambda: Country(code="CN", name="China"))
    favourite_beatmapset_count: int = 0  # TODO
    graveyard_beatmapset_count: int = 0  # TODO
    guest_beatmapset_count: int = 0  # TODO
    loved_beatmapset_count: int = 0  # TODO
    mapping_follower_count: int = 0  # TODO
    nominated_beatmapset_count: int = 0  # TODO
    pending_beatmapset_count: int = 0  # TODO
    ranked_beatmapset_count: int = 0  # TODO
    follow_user_mapping: list[int] = Field(default_factory=list)
    follower_count: int = 0
    friends: list["RelationshipResp"] | None = None
    scores_best_count: int = 0
    scores_first_count: int = 0
    scores_recent_count: int = 0
    scores_pinned_count: int = 0
    account_history: list[UserAccountHistoryResp] = []
    active_tournament_banners: list[dict] = []  # TODO
    kudosu: Kudosu = Field(default_factory=lambda: Kudosu(available=0, total=0))  # TODO
    monthly_playcounts: list[MonthlyPlaycountsResp] = Field(default_factory=list)
    unread_pm_count: int = 0  # TODO
    rank_history: RankHistory | None = None  # TODO
    rank_highest: RankHighest | None = None  # TODO
    statistics: UserStatisticsResp | None = None
    statistics_rulesets: dict[str, UserStatisticsResp] | None = None
    user_achievements: list[UserAchievementResp] = Field(default_factory=list)
    cover_url: str = ""  # deprecated
    team: Team | None = None
    session_verified: bool = True
    daily_challenge_user_stats: DailyChallengeStatsResp | None = None

    # TODO: monthly_playcounts, unread_pm_count， rank_history, user_preferences

    @classmethod
    async def from_db(
        cls,
        obj: User,
        session: AsyncSession,
        include: list[str] = [],
        ruleset: GameMode | None = None,
    ) -> "UserResp":
        from .best_score import BestScore
        from .relationship import Relationship, RelationshipResp, RelationshipType

        u = cls.model_validate(obj.model_dump())
        u.id = obj.id
        u.follower_count = (
            await session.exec(
                select(func.count())
                .select_from(Relationship)
                .where(
                    Relationship.target_id == obj.id,
                    Relationship.type == RelationshipType.FOLLOW,
                )
            )
        ).one()
        u.scores_best_count = (
            await session.exec(
                select(func.count())
                .select_from(BestScore)
                .where(
                    BestScore.user_id == obj.id,
                )
                .limit(200)
            )
        ).one()
        u.cover_url = (
            obj.cover.get(
                "url", "https://assets.ppy.sh/user-profile-covers/default.jpeg"
            )
            if obj.cover
            else "https://assets.ppy.sh/user-profile-covers/default.jpeg"
        )

        if "friends" in include:
            u.friends = [
                await RelationshipResp.from_db(session, r)
                for r in (
                    await session.exec(
                        select(Relationship).where(
                            Relationship.user_id == obj.id,
                            Relationship.type == RelationshipType.FOLLOW,
                        )
                    )
                ).all()
            ]

        if "team" in include:
            if await obj.awaitable_attrs.team_membership:
                assert obj.team_membership
                u.team = obj.team_membership.team

        if "account_history" in include:
            u.account_history = [
                UserAccountHistoryResp.from_db(ah)
                for ah in await obj.awaitable_attrs.account_history
            ]

        if "daily_challenge_user_stats":
            if await obj.awaitable_attrs.daily_challenge_stats:
                assert obj.daily_challenge_stats
                u.daily_challenge_user_stats = DailyChallengeStatsResp.from_db(
                    obj.daily_challenge_stats
                )

        if "statistics" in include:
            current_stattistics = None
            for i in await obj.awaitable_attrs.statistics:
                if i.mode == (ruleset or obj.playmode):
                    current_stattistics = i
                    break
            u.statistics = (
                UserStatisticsResp.from_db(current_stattistics)
                if current_stattistics
                else None
            )

        if "statistics_rulesets" in include:
            u.statistics_rulesets = {
                i.mode.value: UserStatisticsResp.from_db(i)
                for i in await obj.awaitable_attrs.statistics
            }

        if "monthly_playcounts" in include:
            u.monthly_playcounts = [
                MonthlyPlaycountsResp.from_db(pc)
                for pc in await obj.awaitable_attrs.monthly_playcounts
            ]

        if "achievements" in include:
            u.user_achievements = [
                UserAchievementResp.from_db(ua)
                for ua in await obj.awaitable_attrs.achievement
            ]

        return u


ALL_INCLUDED = [
    "friends",
    "team",
    "account_history",
    "daily_challenge_user_stats",
    "statistics",
    "statistics_rulesets",
    "achievements",
    "monthly_playcounts",
]


SEARCH_INCLUDED = [
    "team",
    "daily_challenge_user_stats",
    "statistics",
    "statistics_rulesets",
    "achievements",
    "monthly_playcounts",
]
