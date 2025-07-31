from datetime import datetime
from typing import TYPE_CHECKING, TypedDict, cast

from app.models.beatmap import BeatmapRankStatus, Genre, Language
from app.models.model import UTCBaseModel
from app.models.score import GameMode

from pydantic import BaseModel, model_serializer
from sqlalchemy import DECIMAL, JSON, Column, DateTime, Text
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlmodel import Field, Relationship, SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

if TYPE_CHECKING:
    from .beatmap import Beatmap, BeatmapResp


class BeatmapCovers(SQLModel):
    cover: str
    card: str
    list: str
    slimcover: str
    cover_2_x: str | None = Field(default=None, alias="cover@2x")
    card_2_x: str | None = Field(default=None, alias="card@2x")
    list_2_x: str | None = Field(default=None, alias="list@2x")
    slimcover_2_x: str | None = Field(default=None, alias="slimcover@2x")

    @model_serializer
    def _(self) -> dict[str, str | None]:
        self = cast(dict[str, str | None] | BeatmapCovers, self)
        if isinstance(self, dict):
            return {
                "cover": self["cover"],
                "card": self["card"],
                "list": self["list"],
                "slimcover": self["slimcover"],
                "cover@2x": self.get("cover@2x"),
                "card@2x": self.get("card@2x"),
                "list@2x": self.get("list@2x"),
                "slimcover@2x": self.get("slimcover@2x"),
            }
        else:
            return {
                "cover": self.cover,
                "card": self.card,
                "list": self.list,
                "slimcover": self.slimcover,
                "cover@2x": self.cover_2_x,
                "card@2x": self.card_2_x,
                "list@2x": self.list_2_x,
                "slimcover@2x": self.slimcover_2_x,
            }


class BeatmapHype(BaseModel):
    current: int
    required: int


class BeatmapAvailability(BaseModel):
    more_information: str | None = Field(default=None)
    download_disabled: bool | None = Field(default=None)


class BeatmapNominations(SQLModel):
    current: int | None = Field(default=None)
    required: int | None = Field(default=None)


class BeatmapNomination(TypedDict):
    beatmapset_id: int
    reset: bool
    user_id: int
    rulesets: list[GameMode] | None


class BeatmapDescription(SQLModel):
    bbcode: str | None = None
    description: str | None = None


class BeatmapTranslationText(BaseModel):
    name: str
    id: int | None = None


class BeatmapsetBase(SQLModel, UTCBaseModel):
    # Beatmapset
    artist: str = Field(index=True)
    artist_unicode: str = Field(index=True)
    covers: BeatmapCovers | None = Field(sa_column=Column(JSON))
    creator: str
    favourite_count: int
    nsfw: bool = Field(default=False)
    play_count: int
    preview_url: str
    source: str = Field(default="")

    spotlight: bool = Field(default=False)
    title: str
    title_unicode: str
    user_id: int
    video: bool

    # optional
    # converts: list[Beatmap] = Relationship(back_populates="beatmapset")
    current_nominations: list[BeatmapNomination] | None = Field(
        None, sa_column=Column(JSON)
    )
    description: BeatmapDescription | None = Field(default=None, sa_column=Column(JSON))
    # TODO: discussions: list[BeatmapsetDiscussion] = None
    # TODO: current_user_attributes: Optional[CurrentUserAttributes] = None
    # TODO: events: Optional[list[BeatmapsetEvent]] = None

    pack_tags: list[str] = Field(default=[], sa_column=Column(JSON))
    ratings: list[int] = Field(default=None, sa_column=Column(JSON))
    # TODO: recent_favourites: Optional[list[User]] = None
    # TODO: related_users: Optional[list[User]] = None
    # TODO: user: Optional[User] = Field(default=None)
    track_id: int | None = Field(default=None)  # feature artist?
    # TODO: has_favourited

    # BeatmapsetExtended
    bpm: float = Field(default=0.0, sa_column=Column(DECIMAL(10, 2)))
    can_be_hyped: bool = Field(default=False)
    discussion_locked: bool = Field(default=False)
    last_updated: datetime = Field(sa_column=Column(DateTime))
    ranked_date: datetime | None = Field(default=None, sa_column=Column(DateTime))
    storyboard: bool = Field(default=False)
    submitted_date: datetime = Field(sa_column=Column(DateTime))
    tags: str = Field(default="", sa_column=Column(Text))


class Beatmapset(AsyncAttrs, BeatmapsetBase, table=True):
    __tablename__ = "beatmapsets"  # pyright: ignore[reportAssignmentType]

    id: int | None = Field(default=None, primary_key=True, index=True)
    # Beatmapset
    beatmap_status: BeatmapRankStatus = Field(
        default=BeatmapRankStatus.GRAVEYARD,
    )

    # optional
    beatmaps: list["Beatmap"] = Relationship(back_populates="beatmapset")
    beatmap_genre: Genre = Field(default=Genre.UNSPECIFIED)
    beatmap_language: Language = Field(default=Language.UNSPECIFIED)
    nominations_required: int = Field(default=0)
    nominations_current: int = Field(default=0)

    # BeatmapExtended
    hype_current: int = Field(default=0)
    hype_required: int = Field(default=0)
    availability_info: str | None = Field(default=None)
    download_disabled: bool = Field(default=False)

    @classmethod
    async def from_resp(
        cls, session: AsyncSession, resp: "BeatmapsetResp", from_: int = 0
    ) -> "Beatmapset":
        from .beatmap import Beatmap

        d = resp.model_dump()
        update = {}
        if resp.nominations:
            update["nominations_required"] = resp.nominations.required
            update["nominations_current"] = resp.nominations.current
        if resp.hype:
            update["hype_current"] = resp.hype.current
            update["hype_required"] = resp.hype.required
        if resp.genre:
            update["beatmap_genre"] = Genre(resp.genre.id)
        if resp.language:
            update["beatmap_language"] = Language(resp.language.id)
        beatmapset = Beatmapset.model_validate(
            {
                **d,
                "id": resp.id,
                "beatmap_status": BeatmapRankStatus(resp.ranked),
                "availability_info": resp.availability.more_information,
                "download_disabled": resp.availability.download_disabled or False,
            }
        )
        session.add(beatmapset)
        await session.commit()
        await Beatmap.from_resp_batch(session, resp.beatmaps, from_=from_)
        return beatmapset


class BeatmapsetResp(BeatmapsetBase):
    id: int
    beatmaps: list["BeatmapResp"] = Field(default_factory=list)
    discussion_enabled: bool = True
    status: str
    ranked: int
    legacy_thread_url: str = ""
    is_scoreable: bool
    hype: BeatmapHype | None = None
    availability: BeatmapAvailability
    genre: BeatmapTranslationText | None = None
    language: BeatmapTranslationText | None = None
    nominations: BeatmapNominations | None = None

    @classmethod
    async def from_db(cls, beatmapset: Beatmapset) -> "BeatmapsetResp":
        from .beatmap import BeatmapResp

        beatmaps = [
            await BeatmapResp.from_db(beatmap, from_set=True)
            for beatmap in await beatmapset.awaitable_attrs.beatmaps
        ]
        return cls.model_validate(
            {
                "beatmaps": beatmaps,
                "hype": BeatmapHype(
                    current=beatmapset.hype_current, required=beatmapset.hype_required
                ),
                "availability": BeatmapAvailability(
                    more_information=beatmapset.availability_info,
                    download_disabled=beatmapset.download_disabled,
                ),
                "genre": BeatmapTranslationText(
                    name=beatmapset.beatmap_genre.name,
                    id=beatmapset.beatmap_genre.value,
                ),
                "language": BeatmapTranslationText(
                    name=beatmapset.beatmap_language.name,
                    id=beatmapset.beatmap_language.value,
                ),
                "nominations": BeatmapNominations(
                    required=beatmapset.nominations_required,
                    current=beatmapset.nominations_current,
                ),
                "status": beatmapset.beatmap_status.name.lower(),
                "ranked": beatmapset.beatmap_status.value,
                "is_scoreable": beatmapset.beatmap_status > BeatmapRankStatus.PENDING,
                **beatmapset.model_dump(),
            }
        )
