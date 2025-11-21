"""In-memory task storage for development environment.

This module provides a memory-based alternative to Redis for local development,
eliminating external service dependencies.
"""

import asyncio
import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class InMemoryTaskStore:
    """In-memory task storage with TTL support."""

    def __init__(self):
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._cleanup_task = None
        logger.info("Using in-memory task storage (development mode)")

    async def start(self):
        """Start background cleanup task."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
            logger.debug("Started in-memory task store cleanup task")

    async def stop(self):
        """Stop background cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.debug("Stopped in-memory task store cleanup task")

    async def get(self, key: str) -> Optional[str]:
        """Get task data by key."""
        task_data = self._tasks.get(key)
        if task_data is None:
            return None

        # Check if expired
        if task_data.get("expires_at", 0) < time.time():
            del self._tasks[key]
            return None

        return task_data["data"]

    async def setex(self, key: str, ttl_seconds: int, value: str):
        """Set task data with TTL."""
        expires_at = time.time() + ttl_seconds
        self._tasks[key] = {
            "data": value,
            "expires_at": expires_at,
            "created_at": time.time(),
        }
        logger.debug(f"Stored task {key} with TTL {ttl_seconds}s")

    async def delete(self, key: str):
        """Delete task data."""
        self._tasks.pop(key, None)
        logger.debug(f"Deleted task {key}")

    async def _periodic_cleanup(self):
        """Periodically clean up expired tasks."""
        while True:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes
                current_time = time.time()
                expired_keys = [
                    key
                    for key, task in self._tasks.items()
                    if task["expires_at"] < current_time
                ]
                for key in expired_keys:
                    del self._tasks[key]
                if expired_keys:
                    logger.debug(f"Cleaned up {len(expired_keys)} expired tasks")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")


# Global singleton instance
_task_store: Optional[InMemoryTaskStore] = None


def get_in_memory_task_store() -> InMemoryTaskStore:
    """Get or create the in-memory task store singleton."""
    global _task_store
    if _task_store is None:
        _task_store = InMemoryTaskStore()
    return _task_store
