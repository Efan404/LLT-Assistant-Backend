"""Unit tests for Feature 4: Quality Analysis API.

These tests verify the /quality/analyze endpoint functionality
including success paths and error handling.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.v1.schemas import (
    FixSuggestion,
    QualityAnalysisResponse,
    QualityIssue,
    QualitySummary,
)
from app.main import app


class TestQualityAnalysisAPI:
    """Test suite for /quality/analyze endpoint."""

    def test_quality_analyze_success(self):
        """Test successful quality analysis with valid request."""
        client = TestClient(app)

        # Mock request payload
        request_payload = {
            "files": [
                {
                    "path": "test_example.py",
                    "content": "def test_addition():\n    assert 1 + 1 == 2\n",
                }
            ],
            "mode": "hybrid",
        }

        # Create async mock for the service - patch the function to return our mock
        mock_service = AsyncMock()
        mock_service.analyze_batch = AsyncMock(
            return_value=QualityAnalysisResponse(
                analysis_id="test-123",
                summary=QualitySummary(
                    total_files=1, total_issues=2, critical_issues=1
                ),
                issues=[
                    QualityIssue(
                        file_path="test_example.py",
                        line=2,
                        column=4,
                        severity="warning",
                        code="trivial-assertion",
                        message="Test assertion is trivial",
                        detected_by="rule",
                        suggestion=FixSuggestion(
                            type="replace",
                            new_text="assert result == 2",
                            description="Use a more meaningful assertion",
                        ),
                    ),
                    QualityIssue(
                        file_path="test_example.py",
                        line=1,
                        column=0,
                        severity="info",
                        code="missing-docstring",
                        message="Test function missing docstring",
                        detected_by="llm",
                        suggestion=None,
                    ),
                ],
            )
        )

        with patch("app.api.v1.routes.get_quality_service", return_value=mock_service):
            response = client.post("/api/v1/quality/analyze", json=request_payload)

        # Verify response
        assert response.status_code == 200
        response_data = response.json()

        # Verify response structure matches OpenAPI spec
        assert "analysis_id" in response_data
        assert "summary" in response_data
        assert "issues" in response_data

        # Verify summary
        assert response_data["summary"]["total_files"] == 1
        assert response_data["summary"]["total_issues"] == 2
        assert response_data["summary"]["critical_issues"] == 1

        # Verify issues
        assert len(response_data["issues"]) == 2
        assert response_data["issues"][0]["file_path"] == "test_example.py"
        assert response_data["issues"][0]["severity"] == "warning"
        assert response_data["issues"][0]["detected_by"] == "rule"

        # Verify suggestion
        assert response_data["issues"][0]["suggestion"]["type"] == "replace"
        assert "description" in response_data["issues"][0]["suggestion"]

        # Verify mock was called correctly
        mock_service.analyze_batch.assert_called_once()

    def test_quality_analyze_no_files(self):
        """Test quality analysis fails when files list is empty."""
        client = TestClient(app)

        request_payload = {
            "files": [],  # Empty - should trigger validation error
            "mode": "hybrid",
        }

        response = client.post("/api/v1/quality/analyze", json=request_payload)

        # Should return 400 for validation error
        assert response.status_code == 400
        response_data = response.json()
        assert "detail" in response_data
        assert (
            "files" in response_data["detail"].lower()
            or "empty" in response_data["detail"].lower()
        )

    def test_quality_analyze_missing_files(self):
        """Test quality analysis fails when files field is missing."""
        client = TestClient(app)

        request_payload = {
            # Missing files field
            "mode": "hybrid",
        }

        response = client.post("/api/v1/quality/analyze", json=request_payload)

        # Should return 422 for validation error (missing required field)
        assert response.status_code == 422

    def test_quality_analyze_invalid_mode(self):
        """Test quality analysis fails with invalid mode."""
        client = TestClient(app)

        request_payload = {
            "files": [
                {
                    "path": "test.py",
                    "content": "def test(): pass",
                }
            ],
            "mode": "invalid-mode",
        }

        response = client.post("/api/v1/quality/analyze", json=request_payload)

        # Should return 422 for validation error
        assert response.status_code == 422

    def test_quality_analyze_multiple_files(self):
        """Test quality analysis with multiple files."""
        client = TestClient(app)

        request_payload = {
            "files": [
                {
                    "path": "test_file1.py",
                    "content": "def test_one(): assert True",
                },
                {
                    "path": "test_file2.py",
                    "content": "def test_two(): assert 1 == 1",
                },
                {
                    "path": "test_file3.py",
                    "content": "def test_three(): assert 2 + 2 == 4",
                },
            ],
            "mode": "fast",
        }

        mock_service = AsyncMock()
        mock_service.analyze_batch = AsyncMock(
            return_value=QualityAnalysisResponse(
                analysis_id="test-multi",
                summary=QualitySummary(
                    total_files=3, total_issues=5, critical_issues=2
                ),
                issues=[
                    QualityIssue(
                        file_path="test_file1.py",
                        line=1,
                        column=0,
                        severity="error",
                        code="missing-assertion",
                        message="Missing assertion in test",
                        detected_by="rule",
                        suggestion=None,
                    ),
                ],
            )
        )

        with patch("app.api.v1.routes.get_quality_service", return_value=mock_service):
            response = client.post("/api/v1/quality/analyze", json=request_payload)

        assert response.status_code == 200
        response_data = response.json()

        assert response_data["summary"]["total_files"] == 3
        assert len(response_data["issues"]) >= 1

    def test_quality_analyze_without_suggestions(self):
        """Test quality analysis where some issues have no suggestions."""
        client = TestClient(app)

        request_payload = {
            "files": [
                {
                    "path": "test.py",
                    "content": "def test(): pass",
                }
            ],
            "mode": "fast",
        }

        mock_service = AsyncMock()
        mock_service.analyze_batch = AsyncMock(
            return_value=QualityAnalysisResponse(
                analysis_id="test-no-suggestions",
                summary=QualitySummary(
                    total_files=1, total_issues=1, critical_issues=0
                ),
                issues=[
                    QualityIssue(
                        file_path="test.py",
                        line=1,
                        column=0,
                        severity="info",
                        code="style-issue",
                        message="Minor style issue",
                        detected_by="rule",
                        suggestion=None,  # No suggestion
                    )
                ],
            )
        )

        with patch("app.api.v1.routes.get_quality_service", return_value=mock_service):
            response = client.post("/api/v1/quality/analyze", json=request_payload)

        assert response.status_code == 200
        response_data = response.json()

        # Verify issue without suggestion
        assert response_data["issues"][0]["suggestion"] is None

    def test_quality_analyze_service_exception(self):
        """Test quality analysis handles service exceptions gracefully."""
        client = TestClient(app)

        request_payload = {
            "files": [
                {
                    "path": "test.py",
                    "content": "def test(): pass",
                }
            ],
            "mode": "hybrid",
        }

        mock_service = AsyncMock()
        mock_service.analyze_batch = AsyncMock(side_effect=Exception("Service error"))

        with patch("app.api.v1.routes.get_quality_service", return_value=mock_service):
            response = client.post("/api/v1/quality/analyze", json=request_payload)

        # Should return 500 for internal error
        assert response.status_code == 500
        response_data = response.json()
        assert "detail" in response_data
        assert "internal error" in response_data["detail"].lower()

    def test_quality_analyze_service_initialization_failure(self):
        """Test quality analysis handles service initialization failure."""
        client = TestClient(app)

        request_payload = {
            "files": [
                {
                    "path": "test.py",
                    "content": "def test(): pass",
                }
            ],
            "mode": "hybrid",
        }

        # Mock RuleEngine to raise exception during initialization
        with patch(
            "app.api.v1.routes.RuleEngine", side_effect=Exception("Init failed")
        ):
            response = client.post("/api/v1/quality/analyze", json=request_payload)

        # Should return 503 for service unavailable
        assert response.status_code == 503
        response_data = response.json()
        assert "detail" in response_data
        assert "failed to initialize" in response_data["detail"].lower()

    def test_quality_analyze_response_schema_compliance(self):
        """Test that response matches OpenAPI schema specification."""
        client = TestClient(app)

        request_payload = {
            "files": [
                {
                    "path": "test.py",
                    "content": "def test_example():\n    assert True\n",
                }
            ],
            "mode": "fast",
        }

        mock_service = AsyncMock()
        mock_service.analyze_batch = AsyncMock(
            return_value=QualityAnalysisResponse(
                analysis_id="test-schema",
                summary=QualitySummary(
                    total_files=1, total_issues=2, critical_issues=1
                ),
                issues=[
                    QualityIssue(
                        file_path="test.py",
                        line=1,
                        column=0,
                        severity="error",
                        code="test-error",
                        message="Test error message",
                        detected_by="rule",
                        suggestion=FixSuggestion(
                            type="replace",
                            new_text="fixed code",
                            description="Fix description",
                        ),
                    )
                ],
            )
        )

        with patch("app.api.v1.routes.get_quality_service", return_value=mock_service):
            response = client.post("/api/v1/quality/analyze", json=request_payload)

        assert response.status_code == 200
        response_data = response.json()

        # Verify response follows OpenAPI schema
        # Check required fields exist
        assert isinstance(response_data["summary"], dict)
        assert isinstance(response_data["issues"], list)

        # Check summary structure
        summary = response_data["summary"]
        assert "total_files" in summary
        assert "total_issues" in summary
        assert "critical_issues" in summary
        assert isinstance(summary["total_files"], int)
        assert isinstance(summary["total_issues"], int)
        assert isinstance(summary["critical_issues"], int)

        # Check issues structure
        for issue in response_data["issues"]:
            assert "file_path" in issue
            assert "line" in issue
            assert "severity" in issue
            assert "code" in issue
            assert "message" in issue
            assert "detected_by" in issue

            # Check enum values are valid
            assert issue["severity"] in ["error", "warning", "info"]
            assert issue["detected_by"] in ["rule", "llm"]

            # Check suggestion structure if present
            if issue["suggestion"] is not None:
                suggestion = issue["suggestion"]
                assert "type" in suggestion
                assert suggestion["type"] in ["replace", "delete", "insert"]

    def test_quality_analyze_too_many_files(self):
        """Test quality analysis fails with too many files."""
        client = TestClient(app)

        # Create payload with too many files (exceeds MAX_FILES_PER_REQUEST)
        too_many_files = [
            {"path": f"test_{i}.py", "content": "def test(): pass"}
            for i in range(60)  # Assuming MAX_FILES_PER_REQUEST is 50
        ]

        request_payload = {"files": too_many_files, "mode": "fast"}

        response = client.post("/api/v1/quality/analyze", json=request_payload)

        # Should return 400 for too many files
        assert response.status_code == 400
        response_data = response.json()
        assert "detail" in response_data
        assert "too many" in response_data["detail"].lower()
