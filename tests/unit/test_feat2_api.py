"""Unit tests for Feature 2 (coverage optimization) API contracts.

These tests focus on the request/response shapes for:
- POST /api/v1/optimization/coverage
- GET  /api/v1/tasks/{task_id}

The goal is to keep them aligned with docs/api/openapi.yaml and mirror Feature 1 tests.
"""

from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

import app.api.v1.routes as routes_module
from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class TestCoverageOptimizationWorkflow:
    """Tests for /optimization/coverage endpoint."""

    def test_coverage_optimization_accepts_valid_request_and_returns_async_job_response(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """POST /optimization/coverage validates request and returns AsyncJobResponse."""

        async def fake_create_task(payload: Dict[str, Any]) -> str:  # type: ignore[override]
            # Ensure payload contains required fields
            assert "source_code" in payload
            assert "uncovered_ranges" in payload
            assert isinstance(payload["uncovered_ranges"], list)
            if payload["uncovered_ranges"]:
                # Check structure of first range if present
                first_range = payload["uncovered_ranges"][0]
                assert "start_line" in first_range
                assert "end_line" in first_range
                assert "type" in first_range
            return "123e4567-e89b-12d3-a456-426614174000"

        async def fake_execute_coverage_optimization_task(  # type: ignore[override]
            task_id: str, payload: Dict[str, Any]
        ) -> None:
            # No-op in unit test – background execution is tested elsewhere
            return None

        monkeypatch.setattr(routes_module, "create_task", fake_create_task)
        monkeypatch.setattr(
            routes_module,
            "execute_coverage_optimization_task",
            fake_execute_coverage_optimization_task,
        )

        payload = {
            "source_code": "def calculate_tax(income):\n    if income < 0:\n        raise ValueError\n    return income * 0.2",
            "existing_test_code": "def test_calculate_tax():\n    assert calculate_tax(1000) == 200",
            "uncovered_ranges": [
                {"start_line": 2, "end_line": 3, "type": "branch"},
                {"start_line": 4, "end_line": 4, "type": "line"},
            ],
            "framework": "pytest",
        }

        response = client.post("/api/v1/optimization/coverage", json=payload)

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

    def test_coverage_optimization_missing_required_fields_is_rejected(
        self, client: TestClient
    ) -> None:
        """Requests without required source_code or uncovered_ranges should fail validation."""

        # Missing source_code
        payload = {
            "uncovered_ranges": [{"start_line": 1, "end_line": 2, "type": "line"}]
        }

        response = client.post("/api/v1/optimization/coverage", json=payload)
        assert response.status_code in {400, 422}

        # Missing uncovered_ranges
        payload = {"source_code": "def add(a, b): return a + b"}

        response = client.post("/api/v1/optimization/coverage", json=payload)
        assert response.status_code in {400, 422}

    def test_coverage_optimization_invalid_uncovered_range_format_is_rejected(
        self, client: TestClient
    ) -> None:
        """Invalid uncovered range format should fail validation."""

        # uncovered_ranges should be an array of objects with start_line, end_line, type
        payload = {
            "source_code": "def add(a, b): return a + b",
            "uncovered_ranges": ["invalid", "format"],  # Should be objects, not strings
        }

        response = client.post("/api/v1/optimization/coverage", json=payload)
        assert response.status_code in {400, 422}


class TestCoverageOptimizationTaskStatus:
    """Tests for task status with coverage optimization results."""

    def test_get_task_status_returns_task_status_response_with_coverage_result(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Successful task lookup returns TaskStatusResponse with CoverageOptimizationResult."""

        async def fake_get_task(task_id: str) -> Dict[str, Any]:  # type: ignore[override]
            assert task_id == "123e4567-e89b-12d3-a456-426614174000"
            return {
                "id": task_id,
                "status": "completed",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "result": {
                    "recommended_tests": [
                        {
                            "test_code": "def test_edge_case():\n    assert add(0, 0) == 0",
                            "target_line": 45,
                            "scenario_description": "Test addition with zeros",
                            "expected_coverage_impact": "Covers line 2 branch",
                        }
                    ]
                },
                "error": None,
            }

        monkeypatch.setattr(routes_module, "get_task", fake_get_task)

        response = client.get("/api/v1/tasks/123e4567-e89b-12d3-a456-426614174000")

        assert response.status_code == 200
        data = response.json()

        # TaskStatusResponse contract from OpenAPI:
        # - task_id: string (uuid)
        # - status: [pending, processing, completed, failed]
        # - created_at: date-time
        # - result: CoverageOptimizationResult (list of recommended_tests)
        assert data["task_id"] == "123e4567-e89b-12d3-a456-426614174000"
        assert data["status"] == "completed"

        assert "created_at" in data
        assert isinstance(data["created_at"], str)

        # CoverageOptimizationResult should have recommended_tests array
        result = data.get("result")
        assert isinstance(result, dict)
        assert "recommended_tests" in result
        assert isinstance(result["recommended_tests"], list)

        # Check structure of first recommended test
        if result["recommended_tests"]:
            first_test = result["recommended_tests"][0]
            assert isinstance(first_test, dict)
            assert "test_code" in first_test
            assert isinstance(first_test["test_code"], str)
            assert "target_line" in first_test
            assert isinstance(first_test["target_line"], int)
            assert "scenario_description" in first_test
            assert isinstance(first_test["scenario_description"], str)
            assert "expected_coverage_impact" in first_test
            assert isinstance(first_test["expected_coverage_impact"], str)

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

        response = client.get("/api/v1/tasks/00000000-0000-0000-0000-000000000000")

        assert response.status_code == 404
