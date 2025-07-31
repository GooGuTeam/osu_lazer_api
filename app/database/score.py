import asyncio
from collections.abc import Sequence
from datetime import UTC, date, datetime
import math
from typing import TYPE_CHECKING

from app.calculator import (
    calculate_pp,
    calculate_pp_weight,
    calculate_score_to_level,
    calculate_weighted_acc,
    calculate_weighted_pp,
    clamp,
)
from app.models.beatmap import BeatmapRankStatus
from app.models.model import UTCBaseModel
from app.models.mods import APIMod, mods_can_get_pp
from app.models.score import (
    INT_TO_MODE,
    MODE_TO_INT,
    GameMode,
    HitResult,
    LeaderboardType,
    Rank,
    ScoreStatistics,
    SoloScoreSubmissionInfo,
)

from .beatmap import Beatmap, BeatmapResp
from .beatmapset import BeatmapsetResp
from .best_score import BestScore
from .lazer_user import User, UserResp
from .monthly_playcounts import MonthlyPlaycounts
from .score_token import ScoreToken

from redis import Redis
from sqlalchemy import Column, ColumnExpressionArgument, DateTime
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import aliased
from sqlmodel import (
    JSON,
    BigInteger,
    Field,
    ForeignKey,
    Relationship,
    SQLModel,
    col,
    false,
    func,
    select,
)
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.sql._expression_select_cls import SelectOfScalar

if TYPE_CHECKING:
    from app.fetcher import Fetcher


class ScoreBase(AsyncAttrs, SQLModel, UTCBaseModel):
    # 基本字段
    accuracy: float
    map_md5: str = Field(max_length=32, index=True)
    build_id: int | None = Field(default=None)
    classic_total_score: int | None = Field(
        default=0, sa_column=Column(BigInteger)
    )  # solo_score
    ended_at: datetime = Field(sa_column=Column(DateTime))
    has_replay: bool
    max_combo: int
    mods: list[APIMod] = Field(sa_column=Column(JSON))
    passed: bool
    playlist_item_id: int | None = Field(default=None)  # multiplayer
    pp: float = Field(default=0.0)
    preserve: bool = Field(default=True)
    rank: Rank
    room_id: int | None = Field(default=None)  # multiplayer
    started_at: datetime = Field(sa_column=Column(DateTime))
    total_score: int = Field(default=0, sa_column=Column(BigInteger))
    total_score_without_mods: int = Field(
        default=0, sa_column=Column(BigInteger), exclude=True
    )
    type: str

    # optional
    # TODO: current_user_attributes
    position: int | None = Field(default=None)  # multiplayer


class Score(ScoreBase, table=True):
    __tablename__ = "scores"  # pyright: ignore[reportAssignmentType]
    id: int | None = Field(
        default=None, sa_column=Column(BigInteger, autoincrement=True, primary_key=True)
    )
    beatmap_id: int = Field(index=True, foreign_key="beatmaps.id")
    user_id: int = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            ForeignKey("lazer_users.id"),
            index=True,
        ),
    )
    # ScoreStatistics
    n300: int = Field(exclude=True)
    n100: int = Field(exclude=True)
    n50: int = Field(exclude=True)
    nmiss: int = Field(exclude=True)
    ngeki: int = Field(exclude=True)
    nkatu: int = Field(exclude=True)
    nlarge_tick_miss: int | None = Field(default=None, exclude=True)
    nlarge_tick_hit: int | None = Field(default=None, exclude=True)
    nslider_tail_hit: int | None = Field(default=None, exclude=True)
    nsmall_tick_hit: int | None = Field(default=None, exclude=True)
    gamemode: GameMode = Field(index=True)

    # optional
    beatmap: Beatmap = Relationship()
    user: User = Relationship(sa_relationship_kwargs={"lazy": "joined"})

    @property
    def is_perfect_combo(self) -> bool:
        return self.max_combo == self.beatmap.max_combo

    @staticmethod
    def select_clause_unique(
        *where_clauses: ColumnExpressionArgument[bool] | bool,
    ) -> SelectOfScalar["Score"]:
        rownum = (
            func.row_number()
            .over(
                partition_by=col(Score.user_id), order_by=col(Score.total_score).desc()
            )
            .label("rn")
        )
        subq = select(Score, rownum).where(*where_clauses).subquery()
        best = aliased(Score, subq, adapt_on_names=True)
        return select(best).where(subq.c.rn == 1)


class ScoreResp(ScoreBase):
    id: int
    user_id: int
    is_perfect_combo: bool = False
    legacy_perfect: bool = False
    legacy_total_score: int = 0  # FIXME
    processed: bool = False  # solo_score
    weight: float = 0.0
    best_id: int | None = None
    ruleset_id: int | None = None
    beatmap: BeatmapResp | None = None
    beatmapset: BeatmapsetResp | None = None
    user: UserResp | None = None
    statistics: ScoreStatistics | None = None
    maximum_statistics: ScoreStatistics | None = None
    rank_global: int | None = None
    rank_country: int | None = None

    @classmethod
    async def from_db(
        cls, session: AsyncSession, score: Score, user: User | None = None
    ) -> "ScoreResp":
        s = cls.model_validate(score.model_dump())
        assert score.id
        await score.awaitable_attrs.beatmap
        s.beatmap = await BeatmapResp.from_db(score.beatmap)
        s.beatmapset = await BeatmapsetResp.from_db(score.beatmap.beatmapset)
        s.is_perfect_combo = s.max_combo == s.beatmap.max_combo
        s.legacy_perfect = s.max_combo == s.beatmap.max_combo
        s.ruleset_id = MODE_TO_INT[score.gamemode]
        best_id = await get_best_id(session, score.id)
        if best_id:
            s.best_id = best_id
            s.weight = calculate_pp_weight(best_id - 1)
        s.statistics = {
            HitResult.MISS: score.nmiss,
            HitResult.MEH: score.n50,
            HitResult.OK: score.n100,
            HitResult.GREAT: score.n300,
            HitResult.PERFECT: score.ngeki,
            HitResult.GOOD: score.nkatu,
        }
        if score.nlarge_tick_miss is not None:
            s.statistics[HitResult.LARGE_TICK_MISS] = score.nlarge_tick_miss
        if score.nslider_tail_hit is not None:
            s.statistics[HitResult.SLIDER_TAIL_HIT] = score.nslider_tail_hit
        if score.nsmall_tick_hit is not None:
            s.statistics[HitResult.SMALL_TICK_HIT] = score.nsmall_tick_hit
        if score.nlarge_tick_hit is not None:
            s.statistics[HitResult.LARGE_TICK_HIT] = score.nlarge_tick_hit
        if score.gamemode == GameMode.MANIA:
            s.maximum_statistics = {
                HitResult.PERFECT: score.beatmap.max_combo,
            }
        else:
            s.maximum_statistics = {
                HitResult.GREAT: score.beatmap.max_combo,
            }
        if user:
            s.user = await UserResp.from_db(
                user,
                session,
                include=["statistics", "team", "daily_challenge_user_stats"],
                ruleset=score.gamemode,
            )
        s.rank_global = (
            await get_score_position_by_id(
                session,
                score.map_md5,
                score.id,
                mode=score.gamemode,
                user=user or score.user,
            )
            or None
        )
        s.rank_country = (
            await get_score_position_by_id(
                session,
                score.map_md5,
                score.id,
                score.gamemode,
                user or score.user,
            )
            or None
        )
        return s


async def get_best_id(session: AsyncSession, score_id: int) -> None:
    rownum = (
        func.row_number()
        .over(partition_by=col(BestScore.user_id), order_by=col(BestScore.pp).desc())
        .label("rn")
    )
    subq = select(BestScore, rownum).subquery()
    stmt = select(subq.c.rn).where(subq.c.score_id == score_id)
    result = await session.exec(stmt)
    return result.one_or_none()


async def get_leaderboard(
    session: AsyncSession,
    beatmap_md5: str,
    mode: GameMode,
    type: LeaderboardType = LeaderboardType.GLOBAL,
    mods: list[APIMod] | None = None,
    user: User | None = None,
    limit: int = 50,
) -> list[Score]:
    scores = []
    if type == LeaderboardType.GLOBAL:
        query = (
            select(Score)
            .where(
                col(Beatmap.beatmap_status).in_(
                    [
                        BeatmapRankStatus.RANKED,
                        BeatmapRankStatus.LOVED,
                        BeatmapRankStatus.QUALIFIED,
                        BeatmapRankStatus.APPROVED,
                    ]
                ),
                Score.map_md5 == beatmap_md5,
                Score.gamemode == mode,
                col(Score.passed).is_(True),
                Score.mods == mods if user and user.is_supporter else false(),
            )
            .limit(limit)
            .order_by(
                col(Score.total_score).desc(),
            )
        )
        result = await session.exec(query)
        scores = list[Score](result.all())
    elif type == LeaderboardType.FRIENDS and user and user.is_supporter:
        # TODO
        ...
    elif type == LeaderboardType.TEAM and user and user.team_membership:
        team_id = user.team_membership.team_id
        query = (
            select(Score)
            .join(Beatmap)
            .where(
                Score.map_md5 == beatmap_md5,
                Score.gamemode == mode,
                col(Score.passed).is_(True),
                col(Score.user.team_membership).is_not(None),
                Score.user.team_membership.team_id == team_id,  # pyright: ignore[reportOptionalMemberAccess]
                Score.mods == mods if user and user.is_supporter else false(),
            )
            .limit(limit)
            .order_by(
                col(Score.total_score).desc(),
            )
        )
        result = await session.exec(query)
        scores = list[Score](result.all())
    if user:
        user_score = (
            await session.exec(
                select(Score).where(
                    Score.map_md5 == beatmap_md5,
                    Score.gamemode == mode,
                    Score.user_id == user.id,
                    col(Score.passed).is_(True),
                )
            )
        ).first()
        if user_score and user_score not in scores:
            scores.append(user_score)
    return scores


async def get_score_position_by_user(
    session: AsyncSession,
    beatmap_md5: str,
    user: User,
    mode: GameMode,
    type: LeaderboardType = LeaderboardType.GLOBAL,
    mods: list[APIMod] | None = None,
) -> int:
    where_clause = [
        Score.map_md5 == beatmap_md5,
        Score.gamemode == mode,
        col(Score.passed).is_(True),
        col(Beatmap.beatmap_status).in_(
            [
                BeatmapRankStatus.RANKED,
                BeatmapRankStatus.LOVED,
                BeatmapRankStatus.QUALIFIED,
                BeatmapRankStatus.APPROVED,
            ]
        ),
    ]
    if mods and user.is_supporter:
        where_clause.append(Score.mods == mods)
    else:
        where_clause.append(false())
    if type == LeaderboardType.FRIENDS and user.is_supporter:
        # TODO
        ...
    elif type == LeaderboardType.TEAM and user.team_membership:
        team_id = user.team_membership.team_id
        where_clause.append(
            col(Score.user.team_membership).is_not(None),
        )
        where_clause.append(
            Score.user.team_membership.team_id == team_id,  # pyright: ignore[reportOptionalMemberAccess]
        )
    rownum = (
        func.row_number()
        .over(
            partition_by=Score.map_md5,
            order_by=col(Score.total_score).desc(),
        )
        .label("row_number")
    )
    subq = select(Score, rownum).join(Beatmap).where(*where_clause).subquery()
    stmt = select(subq.c.row_number).where(subq.c.user == user)
    result = await session.exec(stmt)
    s = result.one_or_none()
    return s if s else 0


async def get_score_position_by_id(
    session: AsyncSession,
    beatmap_md5: str,
    score_id: int,
    mode: GameMode,
    user: User | None = None,
    type: LeaderboardType = LeaderboardType.GLOBAL,
    mods: list[APIMod] | None = None,
) -> int:
    where_clause = [
        Score.map_md5 == beatmap_md5,
        Score.id == score_id,
        Score.gamemode == mode,
        col(Score.passed).is_(True),
        col(Beatmap.beatmap_status).in_(
            [
                BeatmapRankStatus.RANKED,
                BeatmapRankStatus.LOVED,
                BeatmapRankStatus.QUALIFIED,
                BeatmapRankStatus.APPROVED,
            ]
        ),
    ]
    if mods and user and user.is_supporter:
        where_clause.append(Score.mods == mods)
    elif mods:
        where_clause.append(false())
    rownum = (
        func.row_number()
        .over(
            partition_by=[col(Score.user_id), col(Score.map_md5)],
            order_by=col(Score.total_score).desc(),
        )
        .label("rownum")
    )
    subq = (
        select(Score.user_id, Score.id, Score.total_score, rownum)
        .join(Beatmap)
        .where(*where_clause)
        .subquery()
    )
    best_scores = aliased(subq)
    overall_rank = (
        func.rank().over(order_by=best_scores.c.total_score.desc()).label("global_rank")
    )
    final_q = (
        select(best_scores.c.id, overall_rank)
        .select_from(best_scores)
        .where(best_scores.c.rownum == 1)
        .subquery()
    )

    stmt = select(final_q.c.global_rank).where(final_q.c.id == score_id)
    result = await session.exec(stmt)
    s = result.one_or_none()
    return s if s else 0


async def get_user_best_score_in_beatmap(
    session: AsyncSession,
    beatmap: int,
    user: int,
    mode: GameMode | None = None,
) -> Score | None:
    return (
        await session.exec(
            select(Score)
            .where(
                Score.gamemode == mode if mode is not None else True,
                Score.beatmap_id == beatmap,
                Score.user_id == user,
            )
            .order_by(col(Score.total_score).desc())
        )
    ).first()


async def get_user_best_pp_in_beatmap(
    session: AsyncSession,
    beatmap: int,
    user: int,
    mode: GameMode,
) -> BestScore | None:
    return (
        await session.exec(
            select(BestScore).where(
                BestScore.beatmap_id == beatmap,
                BestScore.user_id == user,
                BestScore.gamemode == mode,
            )
        )
    ).first()


async def get_user_best_pp(
    session: AsyncSession,
    user: int,
    limit: int = 200,
) -> Sequence[BestScore]:
    return (
        await session.exec(
            select(BestScore)
            .where(BestScore.user_id == user)
            .order_by(col(BestScore.pp).desc())
            .limit(limit)
        )
    ).all()


async def process_user(
    session: AsyncSession, user: User, score: Score, ranked: bool = False
):
    assert user.id
    previous_score_best = await get_user_best_score_in_beatmap(
        session, score.beatmap_id, user.id, score.gamemode
    )
    add_to_db = False
    mouthly_playcount = (
        await session.exec(
            select(MonthlyPlaycounts).where(
                MonthlyPlaycounts.user_id == user.id,
                MonthlyPlaycounts.year == date.today().year,
                MonthlyPlaycounts.month == date.today().month,
            )
        )
    ).first()
    if mouthly_playcount is None:
        mouthly_playcount = MonthlyPlaycounts(
            user_id=user.id, year=date.today().year, month=date.today().month
        )
        add_to_db = True
    statistics = None
    for i in user.statistics:
        if i.mode == score.gamemode.value:
            statistics = i
            break
    if statistics is None:
        raise ValueError(
            f"User {user.id} does not have statistics for mode {score.gamemode.value}"
        )

    # pc, pt, tth, tts
    statistics.total_score += score.total_score
    difference = (
        score.total_score - previous_score_best.total_score
        if previous_score_best and previous_score_best.id != score.id
        else score.total_score
    )
    if difference > 0 and score.passed and ranked:
        match score.rank:
            case Rank.X:
                statistics.grade_ss += 1
            case Rank.XH:
                statistics.grade_ssh += 1
            case Rank.S:
                statistics.grade_s += 1
            case Rank.SH:
                statistics.grade_sh += 1
            case Rank.A:
                statistics.grade_a += 1
        if previous_score_best is not None:
            match previous_score_best.rank:
                case Rank.X:
                    statistics.grade_ss -= 1
                case Rank.XH:
                    statistics.grade_ssh -= 1
                case Rank.S:
                    statistics.grade_s -= 1
                case Rank.SH:
                    statistics.grade_sh -= 1
                case Rank.A:
                    statistics.grade_a -= 1
        statistics.ranked_score += difference
        statistics.level_current = calculate_score_to_level(statistics.ranked_score)
        statistics.maximum_combo = max(statistics.maximum_combo, score.max_combo)
    statistics.play_count += 1
    mouthly_playcount.playcount += 1
    statistics.play_time += int((score.ended_at - score.started_at).total_seconds())
    statistics.count_100 += score.n100 + score.nkatu
    statistics.count_300 += score.n300 + score.ngeki
    statistics.count_50 += score.n50
    statistics.count_miss += score.nmiss
    statistics.total_hits += (
        score.n300 + score.n100 + score.n50 + score.ngeki + score.nkatu
    )

    if score.passed and ranked:
        best_pp_scores = await get_user_best_pp(session, user.id)
        pp_sum = 0.0
        acc_sum = 0.0
        for i, bp in enumerate(best_pp_scores):
            pp_sum += calculate_weighted_pp(bp.pp, i)
            acc_sum += calculate_weighted_acc(bp.acc, i)
        if len(best_pp_scores):
            # https://github.com/ppy/osu-queue-score-statistics/blob/c538ae/osu.Server.Queues.ScoreStatisticsProcessor/Helpers/UserTotalPerformanceAggregateHelper.cs#L41-L45
            acc_sum *= 100 / (20 * (1 - math.pow(0.95, len(best_pp_scores))))
        acc_sum = clamp(acc_sum, 0.0, 100.0)
        statistics.pp = pp_sum
        statistics.hit_accuracy = acc_sum
    if add_to_db:
        session.add(mouthly_playcount)
    await session.commit()
    await session.refresh(user)


async def process_score(
    user: User,
    beatmap_id: int,
    ranked: bool,
    score_token: ScoreToken,
    info: SoloScoreSubmissionInfo,
    fetcher: "Fetcher",
    session: AsyncSession,
    redis: Redis,
) -> Score:
    assert user.id
    can_get_pp = info.passed and ranked and mods_can_get_pp(info.ruleset_id, info.mods)
    score = Score(
        accuracy=info.accuracy,
        max_combo=info.max_combo,
        # maximum_statistics=info.maximum_statistics,
        mods=info.mods,
        passed=info.passed,
        rank=info.rank,
        total_score=info.total_score,
        total_score_without_mods=info.total_score_without_mods,
        beatmap_id=beatmap_id,
        ended_at=datetime.now(UTC),
        gamemode=INT_TO_MODE[info.ruleset_id],
        started_at=score_token.created_at,
        user_id=user.id,
        preserve=info.passed,
        map_md5=score_token.beatmap.checksum,
        has_replay=False,
        type="solo",
        n300=info.statistics.get(HitResult.GREAT, 0),
        n100=info.statistics.get(HitResult.OK, 0),
        n50=info.statistics.get(HitResult.MEH, 0),
        nmiss=info.statistics.get(HitResult.MISS, 0),
        ngeki=info.statistics.get(HitResult.PERFECT, 0),
        nkatu=info.statistics.get(HitResult.GOOD, 0),
        nlarge_tick_miss=info.statistics.get(HitResult.LARGE_TICK_MISS, 0),
        nsmall_tick_hit=info.statistics.get(HitResult.SMALL_TICK_HIT, 0),
        nlarge_tick_hit=info.statistics.get(HitResult.LARGE_TICK_HIT, 0),
        nslider_tail_hit=info.statistics.get(HitResult.SLIDER_TAIL_HIT, 0),
    )
    if can_get_pp:
        beatmap_raw = await fetcher.get_or_fetch_beatmap_raw(redis, beatmap_id)
        pp = await asyncio.get_event_loop().run_in_executor(
            None, calculate_pp, score, beatmap_raw
        )
        score.pp = pp
    session.add(score)
    user_id = user.id
    await session.commit()
    await session.refresh(score)
    if can_get_pp:
        previous_pp_best = await get_user_best_pp_in_beatmap(
            session, beatmap_id, user_id, score.gamemode
        )
        if previous_pp_best is None or score.pp > previous_pp_best.pp:
            assert score.id
            best_score = BestScore(
                user_id=user_id,
                score_id=score.id,
                beatmap_id=beatmap_id,
                gamemode=score.gamemode,
                pp=score.pp,
                acc=score.accuracy,
            )
            session.add(best_score)
            session.delete(previous_pp_best) if previous_pp_best else None
            await session.commit()
            await session.refresh(score)
    await session.refresh(score_token)
    await session.refresh(user)
    return score
