from __future__ import annotations

from .hub import Hub, Client
from app.router.signalr.packet import PacketType


class NotificationsHub(Hub):
    """通知Hub，处理客户端通知相关的WebSocket连接"""

    async def send_welcome_message(self, client: Client) -> None:
        """发送欢迎消息给新连接的客户端"""
        try:
            # 发送通知消息给客户端
            await self.send_packet(
                client,
                PacketType.INVOCATION,
                [
                    {},  # headers
                    None,  # invocation_id (无回调)
                    "UserNotification",  # 方法名
                    [{
                        "text": "欢迎来到咕服！ Welcome to 咕 Server! 🎵",
                        "icon": "FontAwesome.Solid.Heart",
                        "isImportant": True
                    }],  # 参数
                    []  # streams - 空数组而不是None
                ]
            )
        except Exception as e:
            print(f"Failed to send welcome notification: {e}")

    async def subscribe_to_notifications(self, client, user_id: int):
        """订阅用户通知"""
        # TODO: 实现通知订阅逻辑
        pass

    async def unsubscribe_from_notifications(self, client, user_id: int):
        """取消订阅用户通知"""
        # TODO: 实现取消通知订阅逻辑
        pass
