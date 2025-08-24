from datetime import datetime
from typing import ClassVar

from app.models.model import UTCBaseModel
from app.utils import utcnow

from sqlalchemy import Text
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlmodel import BigInteger, Column, DateTime, Field, ForeignKey, SQLModel


class MultiplayerRealtimeRoomEventBase(SQLModel, UTCBaseModel):
    event_type: str = Field(index=True)
    event_detail: str | None = Field(default=None, sa_column=Column(Text))


class MultiplayerRealtimeRoomEvent(AsyncAttrs, MultiplayerRealtimeRoomEventBase, table=True):
    __tablename__: ClassVar[str] = "multiplayer_realtime_room_event"

    id: int | None = Field(default=None, primary_key=True, index=True)

    room_id: int = Field(sa_column=Column(ForeignKey("rooms.id"), index=True, nullable=False))
    playlist_item_id: int | None = Field(
        default=None,
        sa_column=Column(ForeignKey("playlists.id"), index=True, nullable=True),
    )
    user_id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, ForeignKey("lazer_users.id"), index=True, nullable=True),
    )

    created_at: datetime = Field(sa_column=Column(DateTime(timezone=True)), default_factory=utcnow)
    updated_at: datetime = Field(sa_column=Column(DateTime(timezone=True)), default_factory=utcnow)
