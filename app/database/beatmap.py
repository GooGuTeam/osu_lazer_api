from datetime import datetime
from typing import TYPE_CHECKING

from app.models.beatmap import BeatmapRankStatus
from app.models.model import UTCBaseModel
from app.models.score import MODE_TO_INT, GameMode

from .beatmapset import Beatmapset, BeatmapsetResp

from sqlalchemy import DECIMAL, Column, DateTime
from sqlmodel import VARCHAR, Field, Relationship, SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

if TYPE_CHECKING:
    from app.fetcher import Fetcher


class BeatmapOwner(SQLModel):
    id: int
    username: str


class BeatmapBase(SQLModel, UTCBaseModel):
    # Beatmap
    url: str
    mode: GameMode
    beatmapset_id: int = Field(foreign_key="beatmapsets.id", index=True)
    difficulty_rating: float = Field(
        default=0.0, sa_column=Column(DECIMAL(precision=10, scale=6))
    )
    total_length: int
    user_id: int
    version: str

    # optional
    checksum: str = Field(sa_column=Column(VARCHAR(32), index=True))
    current_user_playcount: int = Field(default=0)
    max_combo: int = Field(default=0)
    # TODO: failtimes, owners

    # BeatmapExtended
    ar: float = Field(default=0.0, sa_column=Column(DECIMAL(precision=10, scale=2)))
    cs: float = Field(default=0.0, sa_column=Column(DECIMAL(precision=10, scale=2)))
    drain: float = Field(
        default=0.0,
        sa_column=Column(DECIMAL(precision=10, scale=2)),
    )  # hp
    accuracy: float = Field(
        default=0.0,
        sa_column=Column(DECIMAL(precision=10, scale=2)),
    )  # od
    bpm: float = Field(default=0.0, sa_column=Column(DECIMAL(precision=10, scale=2)))
    count_circles: int = Field(default=0)
    count_sliders: int = Field(default=0)
    count_spinners: int = Field(default=0)
    deleted_at: datetime | None = Field(default=None, sa_column=Column(DateTime))
    hit_length: int = Field(default=0)
    last_updated: datetime = Field(sa_column=Column(DateTime))
    passcount: int = Field(default=0)
    playcount: int = Field(default=0)


class Beatmap(BeatmapBase, table=True):
    __tablename__ = "beatmaps"  # pyright: ignore[reportAssignmentType]
    id: int | None = Field(default=None, primary_key=True, index=True)
    beatmapset_id: int = Field(foreign_key="beatmapsets.id", index=True)
    beatmap_status: BeatmapRankStatus
    # optional
    beatmapset: Beatmapset = Relationship(
        back_populates="beatmaps", sa_relationship_kwargs={"lazy": "selectin"}
    )

    @property
    def can_ranked(self) -> bool:
        return self.beatmap_status > BeatmapRankStatus.PENDING

    @classmethod
    async def from_resp(cls, session: AsyncSession, resp: "BeatmapResp") -> "Beatmap":
        d = resp.model_dump()
        del d["beatmapset"]
        beatmap = Beatmap.model_validate(
            {
                **d,
                "beatmapset_id": resp.beatmapset_id,
                "id": resp.id,
                "beatmap_status": BeatmapRankStatus(resp.ranked),
            }
        )
        session.add(beatmap)
        await session.commit()
        beatmap = (
            await session.exec(select(Beatmap).where(Beatmap.id == resp.id))
        ).first()
        assert beatmap is not None, "Beatmap should not be None after commit"
        return beatmap

    @classmethod
    async def from_resp_batch(
        cls, session: AsyncSession, inp: list["BeatmapResp"], from_: int = 0
    ) -> list["Beatmap"]:
        beatmaps = []
        for resp in inp:
            if resp.id == from_:
                continue
            d = resp.model_dump()
            del d["beatmapset"]
            beatmap = Beatmap.model_validate(
                {
                    **d,
                    "beatmapset_id": resp.beatmapset_id,
                    "id": resp.id,
                    "beatmap_status": BeatmapRankStatus(resp.ranked),
                }
            )
            session.add(beatmap)
            beatmaps.append(beatmap)
        await session.commit()
        return beatmaps

    @classmethod
    async def get_or_fetch(
        cls,
        session: AsyncSession,
        fetcher: "Fetcher",
        bid: int | None = None,
        md5: str | None = None,
    ) -> "Beatmap":
        beatmap = (
            await session.exec(
                select(Beatmap).where(
                    Beatmap.id == bid if bid is not None else Beatmap.checksum == md5
                )
            )
        ).first()
        if not beatmap:
            resp = await fetcher.get_beatmap(bid, md5)
            r = await session.exec(
                select(Beatmapset.id).where(Beatmapset.id == resp.beatmapset_id)
            )
            if not r.first():
                set_resp = await fetcher.get_beatmapset(resp.beatmapset_id)
                await Beatmapset.from_resp(session, set_resp, from_=resp.id)
            return await Beatmap.from_resp(session, resp)
        return beatmap


class BeatmapResp(BeatmapBase):
    id: int
    beatmapset_id: int
    beatmapset: BeatmapsetResp | None = None
    convert: bool = False
    is_scoreable: bool
    status: str
    mode_int: int
    ranked: int
    url: str = ""

    @classmethod
    def from_db(
        cls,
        beatmap: Beatmap,
        query_mode: GameMode | None = None,
        from_set: bool = False,
    ) -> "BeatmapResp":
        beatmap_ = beatmap.model_dump()
        if query_mode is not None and beatmap.mode != query_mode:
            beatmap_["convert"] = True
        beatmap_["is_scoreable"] = beatmap.beatmap_status > BeatmapRankStatus.PENDING
        beatmap_["status"] = beatmap.beatmap_status.name.lower()
        beatmap_["ranked"] = beatmap.beatmap_status.value
        beatmap_["mode_int"] = MODE_TO_INT[beatmap.mode]
        if not from_set:
            beatmap_["beatmapset"] = BeatmapsetResp.from_db(beatmap.beatmapset)
        return cls.model_validate(beatmap_)
