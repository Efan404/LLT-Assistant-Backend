#!/usr/bin/env python3
"""Test the generate-tests API endpoint."""

import asyncio
import json
import time
from urllib.parse import urljoin

import httpx


async def test_generate_tests_api(base_url: str = "http://localhost:8000"):
    """Test the generate-tests workflow."""
    print(f"Testing API at: {base_url}")
    print("=" * 60)

    api_url = urljoin(base_url, "/api/v1/workflows/generate-tests")

    # Test data
    payload = {
        "source_code": "def add(a, b):\n    return a + b",
        "user_description": "Generate pytest tests for simple addition function",
        "existing_test_code": "",
        "context": {"mode": "new"},
    }

    try:
        print("\n1. Submitting test generation task...")
        print(f"POST {api_url}")
        print(f"Payload: {json.dumps(payload, indent=2)}")

        async with httpx.AsyncClient() as client:
            response = await client.post(api_url, json=payload)

        print(f"\nResponse Status: {response.status_code}")
        print(f"Response Body: {json.dumps(response.json(), indent=2)}")

        if response.status_code == 202:
            result = response.json()
            task_id = result.get("task_id")
            status = result.get("status")

            print(f"\n✅ Task submitted successfully!")
            print(f"   Task ID: {task_id}")
            print(f"   Status: {status}")

            if task_id:
                print(f"\n2. Polling task status...")
                await poll_task_status(base_url, task_id)
        else:
            print(f"\n❌ Failed to submit task: {response.text}")

    except Exception as e:
        print(f"\n❌ Error: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()


async def poll_task_status(base_url: str, task_id: str, max_attempts: int = 30):
    """Poll task status until completion or timeout."""
    status_url = urljoin(base_url, f"/api/v1/tasks/{task_id}")

    print(f"GET {status_url}")

    async with httpx.AsyncClient() as client:
        for attempt in range(max_attempts):
            try:
                response = await client.get(status_url)

                if response.status_code == 404:
                    print(f"\n❌ Task not found: {task_id}")
                    return

                if response.status_code != 200:
                    print(f"\n❌ Error: {response.status_code} - {response.text}")
                    return

                result = response.json()
                status = result.get("status")

                if attempt == 0:
                    print(f"Initial status: {status}")
                else:
                    print(f"Poll #{attempt + 1}: status = {status}")

                if status == "completed":
                    print(f"\n✅ Task completed successfully!")
                    print(f"Result: {json.dumps(result.get('result'), indent=2)}")
                    return
                elif status == "failed":
                    print(f"\n❌ Task failed!")
                    print(f"Error: {json.dumps(result.get('error'), indent=2)}")
                    return

                # Still pending or processing
                await asyncio.sleep(2)

            except Exception as e:
                print(f"\n❌ Error polling status: {e}")
                return

    print(f"\n⏱️  Polling timed out after {max_attempts} attempts")


if __name__ == "__main__":
    import sys

    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"

    print("Testing Feature 1 API (Generate Tests)")
    print("Make sure the server is running: uvicorn main:app --reload")

    asyncio.run(test_generate_tests_api(base_url))
