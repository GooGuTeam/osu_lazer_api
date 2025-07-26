from __future__ import annotations

from datetime import datetime

from app.models.notification import (
    Notification,
    NotificationCursor,
    NotificationDetails,
    NotificationsResponse,
    NotificationType,
)
from fastapi import Request

from .api_router import router


@router.get("/notifications", response_model=NotificationsResponse)
async def get_notifications(request: Request):
    """获取通知列表"""
    # 创建示例通知数据
    notification_details = NotificationDetails(
        name="FP",
        type="team",
        title="🤔",
        username="MIKUred",
        cover_url="https://a.ppy.sh/37543382?1740748085.jpeg"
    )
    
    notification = Notification(
        id=847680519,
        name="channel_team",
        created_at=datetime.fromisoformat("2025-05-31T13:10:38+00:00"),
        object_type="channel",
        object_id=58278055,
        source_user_id=37543382,
        is_read=True,
        details=notification_details
    )
    
    notification_type = NotificationType(
        cursor=NotificationCursor(id=840260463),
        name=None,
        total=268
    )
    
    # 生成WebSocket通知端点URL
    base_url = str(request.base_url).rstrip('/')
    ws_url = base_url.replace('http://', 'ws://').replace('https://', 'wss://')
    notification_endpoint = f"{ws_url}/signalr/notifications"
    
    response = NotificationsResponse(
        notifications=[notification],
        timestamp=datetime.utcnow(),
        types=[notification_type],
        notification_endpoint=notification_endpoint
    )
    
    return response