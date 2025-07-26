from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class NotificationDetails(BaseModel):
    """通知详细信息"""
    name: str
    type: str
    title: str
    username: str
    cover_url: str


class Notification(BaseModel):
    """单个通知"""
    id: int
    name: str
    created_at: datetime
    object_type: str
    object_id: int
    source_user_id: int
    is_read: bool
    details: NotificationDetails


class NotificationCursor(BaseModel):
    """通知游标"""
    id: int


class NotificationType(BaseModel):
    """通知类型"""
    cursor: NotificationCursor
    name: Optional[str] = None
    total: int


class NotificationsResponse(BaseModel):
    """通知响应"""
    notifications: list[Notification]
    timestamp: datetime
    types: list[NotificationType]
    notification_endpoint: str
