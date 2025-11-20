"""Async task management utilities backed by Redis."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from redis.asyncio import Redis

from app.config import settings
from app.core.llm_client import create_llm_client

TASK_TTL_SECONDS = 60 * 60 * 24  # 24 hours
TASK_KEY_PREFIX = "task:"
SYSTEM_PROMPT = (
    "You are an expert Python test engineer. Generate high-quality pytest tests, "
    "covering edge cases, error handling, and clear assertions. Ensure the output "
    "is ready to paste into a test file."
)

_redis_client: Optional[Redis] = None
logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Supported task lifecycle states."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


def _task_key(task_id: str) -> str:
    return f"{TASK_KEY_PREFIX}{task_id}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_redis_client() -> Redis:
    global _redis_client
    if _redis_client is None:
        redis_url = settings.redis_url

        # For redis 4.x with rediss://, use ssl_cert_reqs parameter
        if redis_url.startswith("rediss://"):
            import ssl

            _redis_client = Redis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True,
                ssl_cert_reqs=ssl.CERT_NONE,
            )
        else:
            _redis_client = Redis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
    return _redis_client


async def create_task(payload: Dict[str, Any]) -> str:
    """
    Create a new asynchronous task, persist it in Redis, and return its id.
    """

    task_id = str(uuid.uuid4())
    task_data = {
        "id": task_id,
        "status": TaskStatus.PENDING.value,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "result": None,
        "error": None,
        "payload": payload,
    }

    await _save_task(task_id, task_data)
    return task_id


async def get_task(task_id: str) -> Optional[Dict[str, Any]]:
    """Fetch task information from Redis."""

    client = _get_redis_client()
    raw = await client.get(_task_key(task_id))
    return json.loads(raw) if raw else None


async def update_task_status(
    task_id: str,
    status: TaskStatus,
    result: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
) -> None:
    """Update task status, persisting the latest metadata."""

    task = await get_task(task_id)
    if task is None:
        raise ValueError(f"Task {task_id} not found")

    task["status"] = status.value
    task["updated_at"] = _now_iso()
    task["result"] = result
    task["error"] = error

    await _save_task(task_id, task)


async def _save_task(task_id: str, task_data: Dict[str, Any]) -> None:
    client = _get_redis_client()
    await client.setex(
        _task_key(task_id),
        TASK_TTL_SECONDS,
        json.dumps(task_data),
    )


async def execute_generate_tests_task(task_id: str, payload: Dict[str, Any]) -> None:
    """
    Execute test generation task asynchronously using asyncio.
    This replaces the Celery worker implementation.
    """
    try:
        await update_task_status(task_id, TaskStatus.PROCESSING)
        generation = await _generate_tests_from_llm(payload)
        result = {"raw_response": generation}
        await update_task_status(task_id, TaskStatus.COMPLETED, result=result)
        logger.info(f"Task {task_id} completed successfully")
    except Exception as exc:
        logger.error(f"Task {task_id} failed: {exc}", exc_info=True)
        await update_task_status(task_id, TaskStatus.FAILED, error=str(exc))


async def _generate_tests_from_llm(payload: Dict[str, Any]) -> str:
    code_submission = payload.get("code_submission", {})
    code = code_submission.get("code", "")
    description = payload.get("user_description", "")
    metadata = code_submission.get("metadata") or {}
    config = payload.get("config") or {}

    messages = _build_generation_messages(description, code, metadata, config)
    client = create_llm_client()
    try:
        return await client.chat_completion(
            messages=messages,
            temperature=0.2,
            max_tokens=1500,
        )
    finally:
        await client.close()


def _build_generation_messages(
    description: str, code: str, metadata: Dict[str, Any], config: Dict[str, Any]
) -> list[Dict[str, str]]:
    meta_lines = []
    if metadata.get("file_path"):
        meta_lines.append(f"- file_path: {metadata['file_path']}")
    if metadata.get("module_path"):
        meta_lines.append(f"- module_path: {metadata['module_path']}")
    if metadata.get("git_context"):
        git_ctx = metadata["git_context"]
        if git_ctx.get("commit_hash"):
            meta_lines.append(f"- commit: {git_ctx['commit_hash']}")
        if git_ctx.get("branch"):
            meta_lines.append(f"- branch: {git_ctx['branch']}")

    config_lines = []
    if config.get("max_test_count"):
        config_lines.append(f"- max_tests: {config['max_test_count']}")
    if config.get("preferred_style"):
        config_lines.append(f"- preferred_style: {config['preferred_style']}")
    if config.get("auto_review_before_return") is not None:
        config_lines.append(
            f"- auto_review_before_return: {config['auto_review_before_return']}"
        )

    metadata_text = "\n".join(meta_lines) if meta_lines else "None provided."
    config_text = "\n".join(config_lines) if config_lines else "Defaults."

    user_prompt = f"""
User description:
{description.strip() or 'No description provided.'}

Code under test (python):
```python
{code.strip()}
```

Code metadata:
{metadata_text}

Generation preferences:
{config_text}

Requirements:
- Produce ready-to-run pytest code.
- Prefer parametrization where it improves clarity.
- Cover edge cases, invalid inputs, and typical scenarios.
- Return responses as Markdown with python code blocks.
"""

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt.strip()},
    ]
