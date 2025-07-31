from __future__ import annotations

from app.database import Beatmap, Score, ScoreResp, ScoreToken, ScoreTokenResp, User
from app.database.score import process_score, process_user
from app.dependencies.database import get_db, get_redis
from app.dependencies.fetcher import get_fetcher
from app.dependencies.user import get_current_user
from app.models.beatmap import BeatmapRankStatus
from app.models.score import (
    INT_TO_MODE,
    GameMode,
    Rank,
    SoloScoreSubmissionInfo,
)

from .api_router import router

from fastapi import Depends, Form, HTTPException, Query
from pydantic import BaseModel
from redis import Redis
from sqlalchemy.orm import joinedload
from sqlmodel import col, select, true
from sqlmodel.ext.asyncio.session import AsyncSession


class BeatmapScores(BaseModel):
    scores: list[ScoreResp]
    userScore: ScoreResp | None = None


@router.get(
    "/beatmaps/{beatmap}/scores", tags=["beatmap"], response_model=BeatmapScores
)
async def get_beatmap_scores(
    beatmap: int,
    legacy_only: bool = Query(None),  # TODO:加入对这个参数的查询
    mode: GameMode | None = Query(None),
    # mods: List[APIMod] = Query(None), # TODO:加入指定MOD的查询
    type: str = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if legacy_only:
        raise HTTPException(
            status_code=404, detail="this server only contains lazer scores"
        )

    all_scores = (
        await db.exec(
            Score.select_clause_unique(
                Score.beatmap_id == beatmap,
                col(Score.passed).is_(True),
                Score.gamemode == mode if mode is not None else true(),
            )
        )
    ).all()

    user_score = (
        await db.exec(
            Score.select_clause_unique(
                Score.beatmap_id == beatmap,
                Score.user_id == current_user.id,
                col(Score.passed).is_(True),
                Score.gamemode == mode if mode is not None else true(),
            )
        )
    ).first()

    return BeatmapScores(
        scores=[await ScoreResp.from_db(db, score, score.user) for score in all_scores],
        userScore=await ScoreResp.from_db(db, user_score, user_score.user)
        if user_score
        else None,
    )


class BeatmapUserScore(BaseModel):
    position: int
    score: ScoreResp


@router.get(
    "/beatmaps/{beatmap}/scores/users/{user}",
    tags=["beatmap"],
    response_model=BeatmapUserScore,
)
async def get_user_beatmap_score(
    beatmap: int,
    user: int,
    legacy_only: bool = Query(None),
    mode: str = Query(None),
    mods: str = Query(None),  # TODO:添加mods筛选
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if legacy_only:
        raise HTTPException(
            status_code=404, detail="This server only contains non-legacy scores"
        )
    user_score = (
        await db.exec(
            select(Score)
            .where(
                Score.gamemode == mode if mode is not None else True,
                Score.beatmap_id == beatmap,
                Score.user_id == user,
            )
            .order_by(col(Score.total_score).desc())
        )
    ).first()

    if not user_score:
        raise HTTPException(
            status_code=404, detail=f"Cannot find user {user}'s score on this beatmap"
        )
    else:
        return BeatmapUserScore(
            position=user_score.position if user_score.position is not None else 0,
            score=await ScoreResp.from_db(db, user_score, user_score.user),
        )


@router.get(
    "/beatmaps/{beatmap}/scores/users/{user}/all",
    tags=["beatmap"],
    response_model=list[ScoreResp],
)
async def get_user_all_beatmap_scores(
    beatmap: int,
    user: int,
    legacy_only: bool = Query(None),
    ruleset: str = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if legacy_only:
        raise HTTPException(
            status_code=404, detail="This server only contains non-legacy scores"
        )
    all_user_scores = (
        await db.exec(
            select(Score)
            .where(
                Score.gamemode == ruleset if ruleset is not None else True,
                Score.beatmap_id == beatmap,
                Score.user_id == user,
            )
            .order_by(col(Score.classic_total_score).desc())
        )
    ).all()

    return [
        await ScoreResp.from_db(db, score, current_user) for score in all_user_scores
    ]


@router.post(
    "/beatmaps/{beatmap}/solo/scores", tags=["beatmap"], response_model=ScoreTokenResp
)
async def create_solo_score(
    beatmap: int,
    version_hash: str = Form(""),
    beatmap_hash: str = Form(),
    ruleset_id: int = Form(..., ge=0, le=3),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    assert current_user.id
    async with db:
        score_token = ScoreToken(
            user_id=current_user.id,
            beatmap_id=beatmap,
            ruleset_id=INT_TO_MODE[ruleset_id],
        )
        db.add(score_token)
        await db.commit()
        await db.refresh(score_token)
        return ScoreTokenResp.from_db(score_token)


@router.put(
    "/beatmaps/{beatmap}/solo/scores/{token}",
    tags=["beatmap"],
    response_model=ScoreResp,
)
async def submit_solo_score(
    beatmap: int,
    token: int,
    info: SoloScoreSubmissionInfo,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    fetcher=Depends(get_fetcher),
):
    if not info.passed:
        info.rank = Rank.F
    async with db:
        score_token = (
            await db.exec(
                select(ScoreToken)
                .options(joinedload(ScoreToken.beatmap))  # pyright: ignore[reportArgumentType]
                .where(ScoreToken.id == token, ScoreToken.user_id == current_user.id)
            )
        ).first()
        if not score_token or score_token.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Score token not found")
        if score_token.score_id:
            score = (
                await db.exec(
                    select(Score).where(
                        Score.id == score_token.score_id,
                        Score.user_id == current_user.id,
                    )
                )
            ).first()
            if not score:
                raise HTTPException(status_code=404, detail="Score not found")
        else:
            beatmap_status = (
                await db.exec(
                    select(Beatmap.beatmap_status).where(Beatmap.id == beatmap)
                )
            ).first()
            if beatmap_status is None:
                raise HTTPException(status_code=404, detail="Beatmap not found")
            ranked = beatmap_status in {
                BeatmapRankStatus.RANKED,
                BeatmapRankStatus.APPROVED,
            }
            score = await process_score(
                current_user,
                beatmap,
                ranked,
                score_token,
                info,
                fetcher,
                db,
                redis,
            )
            await db.refresh(current_user)
            score_id = score.id
            score_token.score_id = score_id
            await process_user(db, current_user, score, ranked)
            score = (await db.exec(select(Score).where(Score.id == score_id))).first()
            assert score is not None
        return await ScoreResp.from_db(db, score, current_user)
