#!/usr/bin/env python3
"""
Test script to simulate osu! client chat requests
"""

import asyncio
import httpx
import json


async def test_chat_endpoints():
    """Test chat endpoints to debug 422 errors"""

    base_url = "http://localhost:8000"

    # First, we need to get a valid token
    auth_data = {
        "grant_type": "password",
        "client_id": "5",
        "client_secret": "FGc9GAtyHzeQDshWP5Ah7dega8hJACAJpQtw6OXk",
        "username": "Googujiang",  # Assuming this user exists
        "password": "password",  # You'll need to set this
        "scope": "*"
    }

    async with httpx.AsyncClient() as client:
        # Get auth token
        print("=== Getting auth token ===")
        try:
            auth_response = await client.post(
                f"{base_url}/oauth/token",
                data=auth_data
            )
            print(f"Auth response: {auth_response.status_code}")
            print(f"Auth content: {auth_response.text}")

            if auth_response.status_code != 200:
                print("Failed to get auth token, cannot test chat endpoints")
                return

            token_data = auth_response.json()
            access_token = token_data["access_token"]
            print(f"Got token: {access_token[:20]}...")

        except Exception as e:
            print(f"Auth error: {e}")
            return

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        # Test 1: Join channel 0
        print("\n=== Testing join channel 0 ===")
        join_response = await client.put(
            f"{base_url}/api/v2/chat/channels/0/users/1",
            headers=headers
        )
        print(f"Join response: {join_response.status_code}")
        print(f"Join content: {join_response.text}")

        # Test 2: Send a message (test different formats)
        print("\n=== Testing message sending ===")

        # Test with different message formats that osu! might send
        test_messages = [
            # Format 1: What we expect
            {"message": "hello world", "is_action": False, "uuid": "test-uuid-1"},

            # Format 2: Form data instead of JSON
            # This will be tested separately

            # Format 3: String values instead of boolean
            {"message": "hello world 2", "is_action": "false", "uuid": "test-uuid-2"},

            # Format 4: No UUID
            {"message": "hello world 3", "is_action": False},
        ]

        for i, msg_data in enumerate(test_messages):
            print(f"\n--- Test message {i+1}: {msg_data} ---")

            msg_response = await client.post(
                f"{base_url}/api/v2/chat/channels/0/messages",
                headers=headers,
                json=msg_data
            )
            print(f"Message response: {msg_response.status_code}")
            print(f"Message content: {msg_response.text}")

        # Test 3: Try form data (osu! might send form data instead of JSON)
        print("\n=== Testing form data ===")
        form_headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/x-www-form-urlencoded"
        }

        form_data = {
            "message": "hello from form",
            "is_action": "false",
            "uuid": "form-uuid"
        }

        form_response = await client.post(
            f"{base_url}/api/v2/chat/channels/0/messages",
            headers=form_headers,
            data=form_data
        )
        print(f"Form response: {msg_response.status_code}")
        print(f"Form content: {msg_response.text}")


if __name__ == "__main__":
    asyncio.run(test_chat_endpoints())
