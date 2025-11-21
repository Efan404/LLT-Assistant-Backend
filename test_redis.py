#!/usr/bin/env python3
"""Test Redis connection."""

import asyncio
import sys
from urllib.parse import urlparse

from redis.asyncio import Redis


async def test_redis_connection(redis_url: str):
    """Test if Redis connection is working."""
    print(f"Testing Redis connection to: {redis_url}")
    print("-" * 60)

    try:
        # Parse URL to extract components
        parsed = urlparse(redis_url)
        print(f"Host: {parsed.hostname}")
        print(f"Port: {parsed.port}")
        print(f"SSL/TLS: {redis_url.startswith('rediss://')}")

        # Create Redis client
        if redis_url.startswith("rediss://"):
            import ssl

            client = Redis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True,
                ssl_cert_reqs=ssl.CERT_NONE,  # For self-signed certs
            )
        else:
            client = Redis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True,
            )

        # Test connection with PING command
        print("\nAttempting to connect...")
        pong = await client.ping()

        if pong:
            print("✅ Redis connection successful!")
            print(f"   PING response: {pong}")
        else:
            print("❌ Redis PING failed")
            return False

        # Try to set and get a test key
        print("\nTesting SET/GET...")
        await client.set("test:connection", "hello from test script", ex=60)
        value = await client.get("test:connection")
        print(f"✅ SET/GET successful: {value}")

        # Clean up
        await client.delete("test:connection")
        await client.close()

        print("\n✅ All tests passed! Redis is working correctly.")
        return True

    except Exception as e:
        print(f"\n❌ Redis connection failed: {type(e).__name__}")
        print(f"   Error: {str(e)}")
        return False


if __name__ == "__main__":
    # You can pass URL as argument or it will use .env file
    import os

    from dotenv import load_dotenv

    load_dotenv()

    redis_url = sys.argv[1] if len(sys.argv) > 1 else os.getenv("REDIS_URL")

    if not redis_url:
        print("Error: No Redis URL provided. Use: python test_redis.py [REDIS_URL]")
        print("Or set REDIS_URL environment variable")
        sys.exit(1)

    success = asyncio.run(test_redis_connection(redis_url))
    sys.exit(0 if success else 1)
