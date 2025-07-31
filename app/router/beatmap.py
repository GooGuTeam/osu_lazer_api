from __future__ import annotations

import asyncio
import hashlib
import json

from app.calculator import calculate_beatmap_attribute
from app.database import Beatmap, BeatmapResp, User
from app.dependencies.database import get_db, get_redis
from app.dependencies.fetcher import get_fetcher
from app.dependencies.user import get_current_user
from app.fetcher import Fetcher
from app.models.beatmap import BeatmapAttributes
from app.models.mods import APIMod, int_to_mods
from app.models.score import (
    INT_TO_MODE,
    GameMode,
)

from .api_router import router

from fastapi import Depends, HTTPException, Query
from httpx import HTTPError, HTTPStatusError
from pydantic import BaseModel
from redis import Redis
import rosu_pp_py as rosu
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession


@router.get("/beatmaps/lookup", tags=["beatmap"], response_model=BeatmapResp)
async def lookup_beatmap(
    id: int | None = Query(default=None, alias="id"),
    md5: str | None = Query(default=None, alias="checksum"),
    filename: str | None = Query(default=None, alias="filename"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    fetcher: Fetcher = Depends(get_fetcher),
):
    if id is None and md5 is None and filename is None:
        raise HTTPException(
            status_code=400,
            detail="At least one of 'id', 'checksum', or 'filename' must be provided.",
        )
    try:
        beatmap = await Beatmap.get_or_fetch(db, fetcher, bid=id, md5=md5)
    except HTTPError:
        raise HTTPException(status_code=404, detail="Beatmap not found")

    if beatmap is None:
        raise HTTPException(status_code=404, detail="Beatmap not found")

    return await BeatmapResp.from_db(beatmap)


@router.get("/beatmaps/{bid}", tags=["beatmap"], response_model=BeatmapResp)
async def get_beatmap(
    bid: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    fetcher: Fetcher = Depends(get_fetcher),
):
    try:
        beatmap = await Beatmap.get_or_fetch(db, fetcher, bid)
        return await BeatmapResp.from_db(beatmap)
    except HTTPError:
        raise HTTPException(status_code=404, detail="Beatmap not found")


class BatchGetResp(BaseModel):
    beatmaps: list[BeatmapResp]


@router.get("/beatmaps", tags=["beatmap"], response_model=BatchGetResp)
@router.get("/beatmaps/", tags=["beatmap"], response_model=BatchGetResp)
async def batch_get_beatmaps(
    b_ids: list[int] = Query(alias="id", default_factory=list),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not b_ids:
        # select 50 beatmaps by last_updated
        beatmaps = (
            await db.exec(
                select(Beatmap).order_by(col(Beatmap.last_updated).desc()).limit(50)
            )
        ).all()
    else:
        beatmaps = (
            await db.exec(select(Beatmap).where(col(Beatmap.id).in_(b_ids)).limit(50))
        ).all()

    return BatchGetResp(beatmaps=[await BeatmapResp.from_db(bm) for bm in beatmaps])


@router.post(
    "/beatmaps/{beatmap}/attributes",
    tags=["beatmap"],
    response_model=BeatmapAttributes,
)
async def get_beatmap_attributes(
    beatmap: int,
    current_user: User = Depends(get_current_user),
    mods: list[str] = Query(default_factory=list),
    ruleset: GameMode | None = Query(default=None),
    ruleset_id: int | None = Query(default=None),
    redis: Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_db),
    fetcher: Fetcher = Depends(get_fetcher),
):
    mods_ = []
    if mods and mods[0].isdigit():
        mods_ = int_to_mods(int(mods[0]))
    else:
        for i in mods:
            try:
                mods_.append(json.loads(i))
            except json.JSONDecodeError:
                mods_.append(APIMod(acronym=i, settings={}))
    mods_.sort(key=lambda x: x["acronym"])
    if ruleset_id is not None and ruleset is None:
        ruleset = INT_TO_MODE[ruleset_id]
    if ruleset is None:
        beatmap_db = await Beatmap.get_or_fetch(db, fetcher, beatmap)
        ruleset = beatmap_db.mode
    key = (
        f"beatmap:{beatmap}:{ruleset}:"
        f"{hashlib.md5(str(mods_).encode()).hexdigest()}:attributes"
    )
    if redis.exists(key):
        return BeatmapAttributes.model_validate_json(redis.get(key))  # pyright: ignore[reportArgumentType]

    try:
        resp = await fetcher.get_or_fetch_beatmap_raw(redis, beatmap)
        try:
            attr = await asyncio.get_event_loop().run_in_executor(
                None, calculate_beatmap_attribute, resp, ruleset, mods_
            )
        except rosu.ConvertError as e:  # pyright: ignore[reportAttributeAccessIssue]
            raise HTTPException(status_code=400, detail=str(e))
        redis.set(key, attr.model_dump_json())
        return attr
    except HTTPStatusError:
        raise HTTPException(status_code=404, detail="Beatmap not found")
