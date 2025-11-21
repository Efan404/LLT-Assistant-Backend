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
        
        # Generate tests using new request format
        generation_result = await _generate_tests_from_llm(payload)
        
        # Format result as GenerateTestsResult per OpenAPI spec
        result = {
            "generated_code": generation_result["generated_code"],
            "explanation": generation_result["explanation"],
        }
        
        await update_task_status(task_id, TaskStatus.COMPLETED, result=result)
        logger.info(f"Task {task_id} completed successfully")
    except Exception as exc:
        logger.error(f"Task {task_id} failed: {exc}", exc_info=True)
        await update_task_status(task_id, TaskStatus.FAILED, error=str(exc))


async def _generate_tests_from_llm(payload: Dict[str, Any]) -> Dict[str, str]:
    """Generate tests from LLM using new OpenAPI-compliant request format."""
    
    # Extract fields from new flattened schema
    source_code = payload.get("source_code", "")
    user_description = payload.get("user_description", "")
    existing_test_code = payload.get("existing_test_code", "")
    context = payload.get("context", {}) or {}
    
    messages = _build_generation_messages(
        source_code=source_code,
        user_description=user_description,
        existing_test_code=existing_test_code,
        context=context,
    )
    
    client = create_llm_client()
    try:
        raw_response = await client.chat_completion(
            messages=messages,
            temperature=0.2,
            max_tokens=2000,
        )
        
        # Parse response to extract code and explanation
        return _parse_generation_response(raw_response)
    finally:
        await client.close()


def _parse_generation_response(raw_response: str) -> Dict[str, str]:
    """Parse LLM response to extract generated code and explanation."""
    import re
    
    # Try to extract code block
    code_block_pattern = r"```python\n(.*?)\n```"
    code_blocks = re.findall(code_block_pattern, raw_response, re.DOTALL)
    
    if code_blocks:
        generated_code = code_blocks[0].strip()
        # The rest is explanation
        explanation = re.sub(code_block_pattern, "", raw_response, flags=re.DOTALL).strip()
    else:
        # No code block found, treat entire response as code
        generated_code = raw_response.strip()
        explanation = "Generated tests based on provided source code."
    
    return {
        "generated_code": generated_code,
        "explanation": explanation or "Generated tests based on provided source code.",
    }


def _build_generation_messages(
    source_code: str,
    user_description: str,
    existing_test_code: str,
    context: Dict[str, Any],
) -> list[Dict[str, str]]:
    """Build messages for LLM chat completion with new request format."""
    
    # Build context information
    context_lines = []
    if context.get("mode"):
        context_lines.append(f"- mode: {context['mode']}")
    if context.get("target_function"):
        context_lines.append(f"- target_function: {context['target_function']}")
    
    context_text = "\n".join(context_lines) if context_lines else "None provided."
    
    # Build user prompt with new structure
    user_prompt_parts = []
    
    if user_description:
        user_prompt_parts.append(f"User description:\n{user_description.strip()}")
    
    user_prompt_parts.append(f"Source code to test:\n```python\n{source_code.strip()}\n```")
    
    if existing_test_code:
        user_prompt_parts.append(
            f"Existing test code (for context):\n```python\n{existing_test_code.strip()}\n```"
        )
    
    user_prompt_parts.append(f"Context:\n{context_text}")
    
    user_prompt_parts.append("""
Requirements:
- Generate high-quality pytest tests
- Cover edge cases, error handling, and typical scenarios
- Include clear assertions
- Return response with generated code in a Python code block
- Provide brief explanation of what was generated
""")
    
    user_prompt = "\n\n".join(user_prompt_parts)

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt.strip()},
    ]
