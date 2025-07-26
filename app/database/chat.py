from __future__ import annotations

from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.database.user import User


class Channel(SQLModel, table=True):
    """聊天频道"""
    __tablename__ = "channels"  # pyright: ignore[reportAssignmentType]

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=32, unique=True)
    topic: str = Field(max_length=256)
    read_priv: int = Field(default=1)
    write_priv: int = Field(default=2)
    auto_join: bool = Field(default=False)


class ChannelUser(SQLModel, table=True):
    """频道用户关系"""
    __tablename__ = "channel_users"  # pyright: ignore[reportAssignmentType]

    channel_id: int = Field(foreign_key="channels.id", primary_key=True)
    user_id: int = Field(foreign_key="users.id", primary_key=True)
    joined_at: datetime = Field(default_factory=datetime.utcnow)
    last_read_message_id: Optional[int] = Field(default=None)


class ChatMessage(SQLModel, table=True):
    """聊天消息"""
    __tablename__ = "chat_messages"  # pyright: ignore[reportAssignmentType]

    id: Optional[int] = Field(default=None, primary_key=True)
    channel_id: int = Field(foreign_key="channels.id")
    user_id: int = Field(foreign_key="users.id")
    content: str = Field(max_length=16777215)  # mediumtext
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_action: bool = Field(default=False)
    uuid: Optional[str] = Field(default=None, max_length=36)


class UserSilence(SQLModel, table=True):
    """用户静音记录"""
    __tablename__ = "user_silences"  # pyright: ignore[reportAssignmentType]

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    silenced_by: int = Field(foreign_key="users.id")
    reason: str = Field(max_length=512)
    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = Field(default=None)
    is_active: bool = Field(default=True)
