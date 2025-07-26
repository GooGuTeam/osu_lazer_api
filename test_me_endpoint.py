#!/usr/bin/env python3

import asyncio
import json
from fastapi.testclient import TestClient
from main import app

def test_me_endpoint():
    """Test the /me endpoint response format"""
    client = TestClient(app)

    # Test with a mock login or create a test user
    print("Testing /me endpoint...")

    # You might need to add authentication here
    try:
        response = client.get("/me/")
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print("Response JSON:")
            print(json.dumps(data, indent=2, default=str))

            # Check critical fields that cause loading issues
            critical_fields = [
                "id", "username", "country_code", "country",
                "session_verified", "statistics", "daily_challenge_user_stats"
            ]

            print("\n=== Critical Fields Check ===")
            for field in critical_fields:
                if field in data:
                    print(f"✓ {field}: {type(data[field]).__name__}")
                    if field == "country":
                        print(f"  - code: {data[field].get('code', 'MISSING')}")
                        print(f"  - name: {data[field].get('name', 'MISSING')}")
                else:
                    print(f"✗ {field}: MISSING")

        else:
            print(f"Error: {response.text}")

    except Exception as e:
        print(f"Error testing endpoint: {e}")

if __name__ == "__main__":
    test_me_endpoint()
