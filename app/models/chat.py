from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Silence(BaseModel):
    """静音信息"""
    id: int
    user_id: int


class ChatAckResponse(BaseModel):
    """聊天确认响应"""
    silences: list[Silence] = []


class ChatChannel(BaseModel):
    """聊天频道"""
    channel_id: int = Field(alias="id")
    name: str
    description: str = Field(alias="topic")
    type: str = "public"  # "public", "private", "multiplayer", etc.
    last_read_id: Optional[int] = None
    last_message_id: Optional[int] = None

    model_config = {"populate_by_name": True}


class ChatMessage(BaseModel):
    """聊天消息"""
    message_id: Optional[int] = Field(alias="id", default=None)
    user_id: int = Field(alias="sender_id")
    channel_id: int
    content: str
    timestamp: datetime
    is_action: bool = False
    uuid: Optional[str] = None

    model_config = {"populate_by_name": True}


class SendMessageRequest(BaseModel):
    """发送消息请求"""
    content: str = Field(alias="message")
    is_action: bool = False
    uuid: Optional[str] = None

    model_config = {"populate_by_name": True}


class UserPresence(BaseModel):
    """用户在线状态"""
    user_id: int
    game_mode: Optional[str] = None
    activity: Optional[str] = None
    status: str = "online"  # "online", "offline", "idle", "dnd"


class GetUpdatesResponse(BaseModel):
    """获取更新响应"""
    messages: list[ChatMessage] = []
    silences: list[Silence] = []
    presence: Optional[list[UserPresence]] = None
