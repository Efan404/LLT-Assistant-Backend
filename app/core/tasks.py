"""Async task management utilities backed by Redis with in-memory fallback.

Supports both Redis (production) and in-memory storage (development fallback).
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional, Union

# Constants for coverage optimization fallback logic
DEFAULT_TARGET_LINE_START = 50
TARGET_LINE_SPACING = 10
DEFAULT_FALLBACK_TARGET_LINE = 50

import redis.asyncio as redis

from app.config import settings
from app.core.in_memory_tasks import get_in_memory_task_store
from app.core.llm_client import create_llm_client

TASK_TTL_SECONDS = 60 * 60 * 24  # 24 hours
TASK_KEY_PREFIX = "task:"
SYSTEM_PROMPT = (
    "You are an expert Python test engineer. Generate high-quality pytest tests, "
    "covering edge cases, error handling, and clear assertions. Ensure the output "
    "is ready to paste into a test file."
)

_redis_client: Optional[redis.Redis] = None
_in_memory_store: Optional[Any] = None
_use_in_memory = False
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


async def _get_redis_client() -> Optional[redis.Redis]:
    """Get Redis client with error handling. Returns None if connection fails."""
    global _redis_client

    if _redis_client is not None:
        # Test if Redis connection is still alive
        try:
            if await _redis_client.ping():
                return _redis_client
        except Exception:
            logger.warning("Redis connection lost, will attempt reconnection")
            _redis_client = None

    if _redis_client is None:
        redis_url = settings.redis_url
        if not redis_url:
            return None

        try:
            # For redis 4.x with rediss://, use ssl_cert_reqs parameter
            if redis_url.startswith("rediss://"):
                import ssl

                _redis_client = redis.Redis.from_url(
                    redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    ssl_cert_reqs=ssl.CERT_NONE,
                )
            else:
                _redis_client = redis.Redis.from_url(
                    redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                )

            # Test connection
            if await _redis_client.ping():
                logger.info("Redis connection established successfully")
                return _redis_client
            else:
                logger.warning("Redis ping failed, falling back to memory storage")
                _redis_client = None
                return None

        except Exception as e:
            logger.warning(
                f"Failed to connect to Redis ({e}), falling back to memory storage"
            )
            _redis_client = None
            return None

    return _redis_client


async def _get_storage():
    """Get appropriate storage (Redis or in-memory) based on availability."""
    global _use_in_memory, _in_memory_store

    if not _use_in_memory:
        redis_client = await _get_redis_client()
        if redis_client is not None:
            return redis_client

        # Redis not available, switch to in-memory
        _use_in_memory = True
        _in_memory_store = get_in_memory_task_store()
        await _in_memory_store.start()
        logger.info("Switched to in-memory task storage for development")

    return _in_memory_store


async def create_task(payload: Dict[str, Any]) -> str:
    """Create a new asynchronous task and return its id."""
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
    logger.info(f"Created task {task_id}")
    return task_id


async def get_task(task_id: str) -> Optional[Dict[str, Any]]:
    """Fetch task information from storage."""
    storage = await _get_storage()
    key = _task_key(task_id)

    try:
        if _use_in_memory:
            raw = await storage.get(key)
        else:
            raw = await storage.get(key)

        return json.loads(raw) if raw else None
    except Exception as e:
        logger.error(f"Error fetching task {task_id}: {e}")
        return None


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
    logger.debug(f"Updated task {task_id} status to {status.value}")


async def _save_task(task_id: str, task_data: Dict[str, Any]) -> None:
    """Save task data to storage."""
    storage = await _get_storage()
    key = _task_key(task_id)
    json_data = json.dumps(task_data)

    try:
        if _use_in_memory:
            await storage.setex(key, TASK_TTL_SECONDS, json_data)
        else:
            await storage.setex(key, TASK_TTL_SECONDS, json_data)
    except Exception as e:
        logger.error(f"Error saving task {task_id}: {e}")
        raise


async def execute_generate_tests_task(task_id: str, payload: Dict[str, Any]) -> None:
    """Execute test generation task asynchronously."""
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
        explanation = re.sub(
            code_block_pattern, "", raw_response, flags=re.DOTALL
        ).strip()
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

    user_prompt_parts.append(
        f"Source code to test:\n```python\n{source_code.strip()}\n```"
    )

    if existing_test_code:
        user_prompt_parts.append(
            f"Existing test code (for context):\n```python\n{existing_test_code.strip()}\n```"
        )

    user_prompt_parts.append(f"Context:\n{context_text}")

    user_prompt_parts.append(
        """
Requirements:
- Generate high-quality pytest tests
- Cover edge cases, error handling, and typical scenarios
- Include clear assertions
- Return response with generated code in a Python code block
- Provide brief explanation of what was generated
"""
    )

    user_prompt = "\n\n".join(user_prompt_parts)

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt.strip()},
    ]


async def execute_coverage_optimization_task(
    task_id: str, payload: Dict[str, Any]
) -> None:
    """Execute coverage optimization task asynchronously."""
    try:
        await update_task_status(task_id, TaskStatus.PROCESSING)

        # Generate coverage optimization using LLM
        optimization_result = await _generate_coverage_optimization_from_llm(payload)

        # Format result as CoverageOptimizationResult per OpenAPI spec
        result = {
            "recommended_tests": optimization_result["recommended_tests"],
        }

        await update_task_status(task_id, TaskStatus.COMPLETED, result=result)
        logger.info(f"Task {task_id} completed successfully")
    except Exception as exc:
        logger.error(f"Task {task_id} failed: {exc}", exc_info=True)
        await update_task_status(task_id, TaskStatus.FAILED, error=str(exc))


async def _generate_coverage_optimization_from_llm(
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Generate coverage optimization recommendations using LLM."""

    # Extract fields from CoverageOptimizationRequest
    source_code = payload.get("source_code", "")
    existing_test_code = payload.get("existing_test_code", "")
    uncovered_ranges = payload.get("uncovered_ranges", [])
    framework = payload.get("framework", "pytest")

    messages = _build_coverage_optimization_messages(
        source_code=source_code,
        existing_test_code=existing_test_code,
        uncovered_ranges=uncovered_ranges,
        framework=framework,
    )

    client = create_llm_client()
    try:
        raw_response = await client.chat_completion(
            messages=messages,
            temperature=0.2,
            max_tokens=3000,  # May need more tokens for multiple test recommendations
        )

        # Parse response to extract coverage optimization recommendations
        return _parse_coverage_optimization_response(raw_response)
    finally:
        await client.close()


def _parse_coverage_optimization_response(raw_response: str) -> Dict[str, Any]:
    """Parse LLM response to extract coverage optimization recommendations."""
    import re

    # Try to extract JSON block first
    json_block_pattern = r"```json\n(.*?)\n```"
    json_blocks = re.findall(json_block_pattern, raw_response, re.DOTALL)

    if json_blocks:
        try:
            # Parse JSON from code block
            data = json.loads(json_blocks[0].strip())
            if "recommended_tests" in data:
                return data
        except json.JSONDecodeError:
            # If JSON block parsing fails, try parsing the entire response as JSON below
            pass

    # Direct JSON parsing (fallback if no code blocks or JSON block parsing failed)
    try:
        data = json.loads(raw_response.strip())
        if "recommended_tests" in data:
            return data
    except json.JSONDecodeError:
        # Response is not valid JSON, will fall back to extracting code blocks below
        pass

    # Fallback: Try to extract Python code blocks and build recommendations
    code_block_pattern = r"```python\n(.*?)\n```"
    code_blocks = re.findall(code_block_pattern, raw_response, re.DOTALL)

    recommended_tests = []
    for i, code in enumerate(code_blocks):
        # Generate a reasonable target line and description
        target_line = DEFAULT_TARGET_LINE_START + (
            i * TARGET_LINE_SPACING
        )  # Placeholder logic
        scenario_description = f"Test case {i + 1} to cover uncovered code"
        expected_coverage_impact = "Covers previously uncovered lines"

        recommended_tests.append(
            {
                "test_code": code.strip(),
                "target_line": target_line,
                "scenario_description": scenario_description,
                "expected_coverage_impact": expected_coverage_impact,
            }
        )

    # If no code blocks found, create a generic recommendation
    if not recommended_tests:
        recommended_tests.append(
            {
                "test_code": raw_response.strip(),
                "target_line": DEFAULT_FALLBACK_TARGET_LINE,
                "scenario_description": "Generated test based on coverage analysis",
                "expected_coverage_impact": "Improves overall coverage",
            }
        )

    return {"recommended_tests": recommended_tests}


def _build_coverage_optimization_messages(
    source_code: str,
    existing_test_code: str,
    uncovered_ranges: list,
    framework: str,
) -> list[Dict[str, str]]:
    """Build messages for LLM coverage optimization chat completion."""

    # Format uncovered ranges for the prompt
    ranges_text = ""
    for i, rng in enumerate(uncovered_ranges, 1):
        start_line = rng.get("start_line", "unknown")
        end_line = rng.get("end_line", "unknown")
        rng_type = rng.get("type", "unknown")
        ranges_text += f"  {i}. Lines {start_line}-{end_line} ({rng_type} coverage)\n"

    if not ranges_text:
        ranges_text = "  No specific uncovered ranges provided.\n"

    user_prompt = f"""
You are an expert Python test engineer specializing in coverage optimization.

**Source code to increase coverage:**
```python
{source_code.strip()}
```

**Current test code (for context):**
```python
{existing_test_code.strip() if existing_test_code else "# No existing tests"}
```

**Uncovered ranges identified by coverage analysis:**
{ranges_text}

**Framework:** {framework}

**Your task:**
Generate targeted test cases to fill these specific coverage gaps.
Focus on:
1. Testing the exact uncovered lines/ranges
2. Edge cases that might not be covered
3. Clear, maintainable test code

**Output format:**
Provide a JSON object with a "recommended_tests" array containing:
- "test_code": Python code for the test
- "target_line": Suggested line number to add this test
- "scenario_description": Brief description of what this test covers
- "expected_coverage_impact": What lines/branches this will cover

Example output:
```json
{{
  "recommended_tests": [
    {{
      "test_code": "def test_add_negative_numbers():\\n    assert add(-1, -2) == -3",
      "target_line": 42,
      "scenario_description": "Test addition with negative numbers",
      "expected_coverage_impact": "Covers line 5-6 in calculate_tax function"
    }}
  ]
}}
```
"""

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt.strip()},
    ]


async def cleanup_task_storage():
    """Cleanup task storage on shutdown."""
    global _in_memory_store

    if _in_memory_store:
        await _in_memory_store.stop()
        _in_memory_store = None
        logger.info("Task storage cleanup completed")
