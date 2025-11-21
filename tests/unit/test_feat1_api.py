"""Unit tests for Feature 1 (test generation) API contracts.

These tests focus on the request/response shapes for:
- POST /api/v1/workflows/generate-tests
- GET  /api/v1/tasks/{task_id}

The goal is to keep them aligned with docs/api/openapi.yaml.
"""

from datetime import datetime, timezone
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

import app.api.v1.routes as routes_module
from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TestGenerateTestsWorkflow:
    """Tests for /workflows/generate-tests endpoint."""

    def test_generate_tests_accepts_new_schema_and_returns_async_job_response(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """POST /workflows/generate-tests uses new schema and AsyncJobResponse."""

        async def fake_create_task(payload: Dict[str, Any]) -> str:  # type: ignore[override]
            # Ensure payload already follows the new flattened schema
            assert "source_code" in payload
            assert isinstance(payload["source_code"], str)
            # Optional fields should not be required
            assert "existing_test_code" in payload
            return "123e4567-e89b-12d3-a456-426614174000"

        async def fake_execute_generate_tests_task(  # type: ignore[override]
            task_id: str, payload: Dict[str, Any]
        ) -> None:
            # No-op in unit test – background execution is tested elsewhere
            return None

        monkeypatch.setattr(routes_module, "create_task", fake_create_task)
        monkeypatch.setattr(
            routes_module,
            "execute_generate_tests_task",
            fake_execute_generate_tests_task,
        )

        payload = {
            "source_code": "def add(a, b): return a + b",
            "user_description": "Generate tests for simple addition",
            "existing_test_code": "def test_add(): assert add(1, 2) == 3",
            "context": {
                "mode": "new",
                "target_function": "add",
            },
        }

        response = client.post("/api/v1/workflows/generate-tests", json=payload)

        assert response.status_code == 202
        data = response.json()

        # AsyncJobResponse contract from OpenAPI:
        # - task_id: string (uuid)
        # - status: one of [pending, processing]
        assert "task_id" in data
        assert data["task_id"] == "123e4567-e89b-12d3-a456-426614174000"

        assert "status" in data
        assert data["status"] in {"pending", "processing"}

        # estimated_time_seconds is optional in the spec, only check type when present
        if (
            "estimated_time_seconds" in data
            and data["estimated_time_seconds"] is not None
        ):
            assert isinstance(data["estimated_time_seconds"], int)

    def test_generate_tests_missing_source_code_is_rejected(
        self, client: TestClient
    ) -> None:
        """Requests without required source_code should fail validation."""

        payload = {
            # "source_code" is intentionally omitted
            "user_description": "Should be rejected",
        }

        response = client.post("/api/v1/workflows/generate-tests", json=payload)

        # Depending on implementation this may be 400 (BadRequest) or 422 (validation error)
        assert response.status_code in {400, 422}


class TestTaskStatusEndpoint:
    """Tests for /tasks/{task_id} endpoint."""

    def test_get_task_status_returns_task_status_response_with_generate_tests_result(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Successful task lookup returns TaskStatusResponse with GenerateTestsResult."""

        async def fake_get_task(task_id: str) -> Dict[str, Any]:  # type: ignore[override]
            assert task_id == "123e4567-e89b-12d3-a456-426614174000"
            return {
                "id": task_id,
                "status": "completed",
                "created_at": _iso_now(),
                "updated_at": _iso_now(),
                "result": {
                    "generated_code": "def test_add(): assert add(1, 2) == 3",
                    "explanation": "Covers basic happy-path addition.",
                },
                "error": None,
            }

        monkeypatch.setattr(routes_module, "get_task", fake_get_task)

        response = client.get(
            "/api/v1/tasks/123e4567-e89b-12d3-a456-426614174000",
        )

        assert response.status_code == 200
        data = response.json()

        # TaskStatusResponse contract from OpenAPI:
        # - task_id: string (uuid)
        # - status: [pending, processing, completed, failed]
        # - created_at: date-time
        # - result: object (GenerateTestsResult for Feature 1)
        assert data["task_id"] == "123e4567-e89b-12d3-a456-426614174000"
        assert data["status"] == "completed"

        assert "created_at" in data
        assert isinstance(data["created_at"], str)

        result = data.get("result")
        assert isinstance(result, dict)
        assert result.get("generated_code")
        assert isinstance(result["generated_code"], str)
        assert result.get("explanation")
        assert isinstance(result["explanation"], str)

        # For a successful task, error should be null or absent
        if "error" in data:
            assert data["error"] is None

    def test_get_task_status_returns_404_when_task_not_found(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Missing task should result in 404 according to the spec."""

        async def fake_get_task(task_id: str) -> None:  # type: ignore[override]
            return None

        monkeypatch.setattr(routes_module, "get_task", fake_get_task)

        response = client.get(
            "/api/v1/tasks/00000000-0000-0000-0000-000000000000",
        )

        assert response.status_code == 404
