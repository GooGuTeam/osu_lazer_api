#!/usr/bin/env python3
"""
Test script for the mark-as-read endpoint
Based on the osu! API implementation pattern
"""

import asyncio
import requests
import json
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8000"
TEST_USERNAME = "test_user"  # Replace with actual test user
TEST_PASSWORD = "test_password"  # Replace with actual test password


def get_auth_token():
    """获取认证令牌"""
    login_data = {
        "username": TEST_USERNAME,
        "password": TEST_PASSWORD
    }

    response = requests.post(f"{BASE_URL}/auth/login", data=login_data)
    if response.status_code == 200:
        token_data = response.json()
        return token_data.get("access_token")
    else:
        print(f"Login failed: {response.status_code} - {response.text}")
        return None


def test_mark_as_read_endpoint():
    """测试标记为已读的端点"""

    # 获取认证令牌
    token = get_auth_token()
    if not token:
        print("Failed to get authentication token")
        return

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    print("🔐 Authentication successful")

    # 1. 获取可用频道
    print("\n📋 Getting available channels...")
    channels_response = requests.get(f"{BASE_URL}/api/v2/chat/channels", headers=headers)

    if channels_response.status_code != 200:
        print(f"❌ Failed to get channels: {channels_response.status_code}")
        return

    channels = channels_response.json()
    print(f"✅ Found {len(channels)} channels")

    if not channels:
        print("No channels available for testing")
        return

    # 使用第一个频道进行测试
    test_channel = channels[0]
    channel_id = test_channel["channel_id"]

    print(f"🎯 Testing with channel: {test_channel['name']} (ID: {channel_id})")
    print(f"   Last read ID: {test_channel.get('last_read_id')}")
    print(f"   Last message ID: {test_channel.get('last_message_id')}")

    # 2. 加入频道（如果还没有加入）
    print(f"\n👥 Joining channel {channel_id}...")
    join_response = requests.put(
        f"{BASE_URL}/api/v2/chat/channels/{channel_id}/users/1",  # Assuming user ID 1
        headers=headers
    )

    if join_response.status_code not in [200, 201]:
        print(f"⚠️ Join response: {join_response.status_code} - {join_response.text}")
    else:
        print("✅ Successfully joined channel")

    # 3. 获取频道消息
    print(f"\n📨 Getting messages from channel {channel_id}...")
    messages_response = requests.get(
        f"{BASE_URL}/api/v2/chat/channels/{channel_id}/messages",
        headers=headers
    )

    if messages_response.status_code != 200:
        print(f"❌ Failed to get messages: {messages_response.status_code}")
        return

    messages = messages_response.json()
    print(f"✅ Found {len(messages)} messages")

    if not messages:
        print("No messages in channel, creating a test message...")

        # 发送测试消息
        test_message = {
            "message": f"Test message at {datetime.now().isoformat()}",
            "is_action": False
        }

        send_response = requests.post(
            f"{BASE_URL}/api/v2/chat/channels/{channel_id}/messages",
            headers=headers,
            json=test_message
        )

        if send_response.status_code == 200:
            sent_message = send_response.json()
            messages = [sent_message]
            print(f"✅ Created test message with ID: {sent_message['message_id']}")
        else:
            print(f"❌ Failed to send test message: {send_response.status_code}")
            return

    # 4. 测试标记为已读
    if messages:
        latest_message = messages[-1]  # 最新消息
        message_id = latest_message["message_id"]

        print(f"\n📍 Marking channel {channel_id} as read up to message {message_id}...")

        mark_read_response = requests.put(
            f"{BASE_URL}/api/v2/chat/channels/{channel_id}/mark-as-read/{message_id}",
            headers=headers
        )

        print(f"   Status: {mark_read_response.status_code}")
        print(f"   Response: {mark_read_response.text}")

        if mark_read_response.status_code == 200:
            print("✅ Successfully marked channel as read")

            # 验证更新：重新获取频道信息
            print("\n🔍 Verifying update...")
            updated_channels_response = requests.get(f"{BASE_URL}/api/v2/chat/channels", headers=headers)

            if updated_channels_response.status_code == 200:
                updated_channels = updated_channels_response.json()
                updated_channel = next((ch for ch in updated_channels if ch["channel_id"] == channel_id), None)

                if updated_channel:
                    print(f"   Updated last read ID: {updated_channel.get('last_read_id')}")

                    if updated_channel.get('last_read_id') == message_id:
                        print("✅ Mark as read operation verified successfully!")
                    else:
                        print("⚠️ Last read ID doesn't match expected value")
                else:
                    print("❌ Channel not found in updated response")
            else:
                print("❌ Failed to verify update")
        else:
            print(f"❌ Failed to mark as read: {mark_read_response.status_code}")

    # 5. 测试错误情况
    print(f"\n🧪 Testing error cases...")

    # 测试不存在的消息ID
    invalid_message_id = 999999
    error_response = requests.put(
        f"{BASE_URL}/api/v2/chat/channels/{channel_id}/mark-as-read/{invalid_message_id}",
        headers=headers
    )

    print(f"   Invalid message ID test: {error_response.status_code}")
    if error_response.status_code == 404:
        print("✅ Correctly rejected invalid message ID")
    else:
        print("⚠️ Unexpected response for invalid message ID")

    # 测试不存在的频道ID
    invalid_channel_id = 999999
    error_response2 = requests.put(
        f"{BASE_URL}/api/v2/chat/channels/{invalid_channel_id}/mark-as-read/1",
        headers=headers
    )

    print(f"   Invalid channel ID test: {error_response2.status_code}")
    if error_response2.status_code == 404:
        print("✅ Correctly rejected invalid channel ID")
    else:
        print("⚠️ Unexpected response for invalid channel ID")


if __name__ == "__main__":
    print("🚀 Testing mark-as-read endpoint...")
    test_mark_as_read_endpoint()
    print("\n🏁 Test completed!")
