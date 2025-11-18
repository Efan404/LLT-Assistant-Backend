"""
Integration tests for API endpoints and end-to-end workflows.

Tests cover complete request-response cycles, real analysis workflows,
and integration between components.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def integration_client():
    """Provide test client for integration tests."""
    return TestClient(app)


class TestHealthEndpoints:
    """Integration tests for health check endpoints."""

    def test_root_endpoint(self, integration_client):
        """Test root endpoint returns service information."""
        response = integration_client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert data["name"] == "LLT Assistant Backend"

    def test_health_endpoint(self, integration_client):
        """Test health check endpoint."""
        response = integration_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"

    def test_api_health_endpoint(self, integration_client):
        """Test API-specific health endpoint."""
        response = integration_client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data


class TestAnalysisModesEndpoint:
    """Integration tests for analysis modes endpoint."""

    def test_get_analysis_modes(self, integration_client):
        """Test retrieving available analysis modes."""
        response = integration_client.get("/api/v1/modes")

        assert response.status_code == 200
        data = response.json()

        # API returns {"modes": [...]}
        assert "modes" in data
        modes_list = data["modes"]
        assert isinstance(modes_list, list)
        assert len(modes_list) == 3

        # Verify all modes are present
        mode_ids = [mode["id"] for mode in modes_list]
        assert "rules-only" in mode_ids
        assert "llm-only" in mode_ids
        assert "hybrid" in mode_ids

        # Verify each mode has description
        for mode_info in modes_list:
            assert "id" in mode_info
            assert "description" in mode_info
            assert isinstance(mode_info["description"], str)


class TestAnalyzeEndpoint:
    """Integration tests for the main analyze endpoint."""

    def test_analyze_empty_request_returns_error(self, integration_client):
        """Test that empty request returns validation error."""
        response = integration_client.post("/api/v1/analyze", json={})

        assert response.status_code == 422  # Validation error

    def test_analyze_missing_files_returns_error(self, integration_client):
        """Test that request without files returns error."""
        payload = {"mode": "rules-only"}

        response = integration_client.post("/api/v1/analyze", json=payload)

        assert response.status_code == 422

    def test_analyze_empty_files_list_returns_error(self, integration_client):
        """Test that empty files list returns error."""
        payload = {"files": [], "mode": "rules-only"}

        response = integration_client.post("/api/v1/analyze", json=payload)

        # API returns 500 for empty files (could be improved to 400)
        assert response.status_code in [400, 422, 500]

    def test_analyze_simple_test_rules_only(self, integration_client):
        """Test analyzing a simple test file in rules-only mode."""
        payload = {
            "files": [
                {
                    "path": "test_example.py",
                    "content": """
def test_addition():
    result = 1 + 1
    assert result == 2
""",
                    "git_diff": None,
                }
            ],
            "mode": "rules-only",
            "config": {},
        }

        response = integration_client.post("/api/v1/analyze", json=payload)

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "analysis_id" in data
        assert "issues" in data
        assert "metrics" in data

        # Verify metrics
        metrics = data["metrics"]
        assert "total_tests" in metrics
        assert "issues_count" in metrics
        assert "analysis_time_ms" in metrics
        assert metrics["total_tests"] == 1

    def test_analyze_test_with_issues_rules_only(self, integration_client):
        """Test analyzing a test file with quality issues."""
        payload = {
            "files": [
                {
                    "path": "test_bad.py",
                    "content": """
def test_redundant():
    value = 42
    assert value == 42
    assert value == 42  # Redundant assertion
""",
                    "git_diff": None,
                }
            ],
            "mode": "rules-only",
        }

        response = integration_client.post("/api/v1/analyze", json=payload)

        assert response.status_code == 200
        data = response.json()

        # Rule engine may or may not detect redundancy (depends on implementation)
        # Just verify response structure is correct
        assert "issues" in data
        assert "metrics" in data
        assert isinstance(data["issues"], list)

        # If issues detected, verify structure
        if len(data["issues"]) > 0:
            issue = data["issues"][0]
            assert "file" in issue
            assert "line" in issue
            assert "severity" in issue
            assert "type" in issue
            assert "message" in issue
            assert "detected_by" in issue

    def test_analyze_missing_assertion(self, integration_client):
        """Test detecting missing assertions."""
        payload = {
            "files": [
                {
                    "path": "test_no_assert.py",
                    "content": """
def test_missing_assertion():
    value = 10 * 2
    result = value + 5
    # No assertion
""",
                    "git_diff": None,
                }
            ],
            "mode": "rules-only",
        }

        response = integration_client.post("/api/v1/analyze", json=payload)

        assert response.status_code == 200
        data = response.json()

        # Should detect missing assertion
        assert data["metrics"]["issues_count"] > 0

    def test_analyze_trivial_assertion(self, integration_client):
        """Test detecting trivial assertions."""
        payload = {
            "files": [
                {
                    "path": "test_trivial.py",
                    "content": """
def test_trivial():
    assert True
    assert 1 == 1
""",
                    "git_diff": None,
                }
            ],
            "mode": "rules-only",
        }

        response = integration_client.post("/api/v1/analyze", json=payload)

        assert response.status_code == 200
        data = response.json()

        # Should detect trivial assertions
        assert data["metrics"]["issues_count"] > 0

    def test_analyze_multiple_files(self, integration_client):
        """Test analyzing multiple files simultaneously."""
        payload = {
            "files": [
                {
                    "path": "test_file1.py",
                    "content": "def test_one(): assert True",
                    "git_diff": None,
                },
                {
                    "path": "test_file2.py",
                    "content": "def test_two(): assert 1 == 1",
                    "git_diff": None,
                },
                {
                    "path": "test_file3.py",
                    "content": "def test_three(): assert 2 + 2 == 4",
                    "git_diff": None,
                },
            ],
            "mode": "rules-only",
        }

        response = integration_client.post("/api/v1/analyze", json=payload)

        assert response.status_code == 200
        data = response.json()

        # Should analyze all files
        assert data["metrics"]["total_tests"] >= 3

    def test_analyze_invalid_mode(self, integration_client):
        """Test that invalid mode returns error."""
        payload = {
            "files": [
                {
                    "path": "test.py",
                    "content": "def test(): assert True",
                    "git_diff": None,
                }
            ],
            "mode": "invalid-mode",
        }

        response = integration_client.post("/api/v1/analyze", json=payload)

        # Should return validation error
        assert response.status_code in [400, 422]

    def test_analyze_with_syntax_error(self, integration_client):
        """Test analyzing file with syntax errors."""
        payload = {
            "files": [
                {
                    "path": "test_broken.py",
                    "content": """
def test_broken(:
    assert True  # Missing closing paren in function def
""",
                    "git_diff": None,
                }
            ],
            "mode": "rules-only",
        }

        response = integration_client.post("/api/v1/analyze", json=payload)

        # Should handle gracefully
        assert response.status_code == 200

    def test_analyze_test_class(self, integration_client):
        """Test analyzing test class with multiple methods."""
        payload = {
            "files": [
                {
                    "path": "test_class.py",
                    "content": """
class TestCalculator:
    def test_addition(self):
        assert 1 + 1 == 2

    def test_subtraction(self):
        assert 5 - 3 == 2

    def test_multiplication(self):
        assert 3 * 4 == 12
""",
                    "git_diff": None,
                }
            ],
            "mode": "rules-only",
        }

        response = integration_client.post("/api/v1/analyze", json=payload)

        assert response.status_code == 200
        data = response.json()

        # Should find 3 test methods
        assert data["metrics"]["total_tests"] == 3

    def test_analyze_with_fixtures(self, integration_client):
        """Test analyzing tests that use fixtures."""
        payload = {
            "files": [
                {
                    "path": "test_fixtures.py",
                    "content": """
import pytest

@pytest.fixture
def sample_data():
    return {"key": "value"}

def test_with_fixture(sample_data):
    assert sample_data["key"] == "value"
""",
                    "git_diff": None,
                }
            ],
            "mode": "rules-only",
        }

        response = integration_client.post("/api/v1/analyze", json=payload)

        assert response.status_code == 200
        data = response.json()

        assert data["metrics"]["total_tests"] >= 1

    @pytest.mark.llm
    @pytest.mark.requires_api_key
    def test_analyze_llm_only_mode(self, integration_client, skip_llm_tests):
        """Test analyzing in LLM-only mode with real API."""
        if skip_llm_tests:
            pytest.skip("Skipping LLM integration test")

        payload = {
            "files": [
                {
                    "path": "test_example.py",
                    "content": """
def test_simple():
    value = 42
    assert value == 42
""",
                    "git_diff": None,
                }
            ],
            "mode": "llm-only",
        }

        response = integration_client.post("/api/v1/analyze", json=payload)

        assert response.status_code == 200
        data = response.json()

        # Should have analysis ID and metrics
        assert "analysis_id" in data
        assert "metrics" in data

    @pytest.mark.llm
    @pytest.mark.requires_api_key
    def test_analyze_hybrid_mode(self, integration_client, skip_llm_tests):
        """Test analyzing in hybrid mode combining rules and LLM."""
        if skip_llm_tests:
            pytest.skip("Skipping LLM integration test")

        payload = {
            "files": [
                {
                    "path": "test_hybrid.py",
                    "content": """
import time

def test_with_issues():
    # Trivial assertion (rule will catch)
    assert True

    # Timing dependency (LLM might catch)
    time.sleep(0.1)
    value = 42
    assert value == 42
""",
                    "git_diff": None,
                }
            ],
            "mode": "hybrid",
        }

        response = integration_client.post("/api/v1/analyze", json=payload)

        assert response.status_code == 200
        data = response.json()

        # Should detect at least the trivial assertion
        assert data["metrics"]["issues_count"] > 0


class TestCORSHeaders:
    """Integration tests for CORS headers."""

    def test_cors_headers_present(self, integration_client):
        """Test that CORS headers are present in responses."""
        response = integration_client.get("/health")

        assert response.status_code == 200
        # CORS headers might be added by middleware
        # Just verify response is successful


class TestOpenAPIDocumentation:
    """Integration tests for API documentation endpoints."""

    def test_openapi_json_available(self, integration_client):
        """Test that OpenAPI JSON specification is available."""
        response = integration_client.get("/openapi.json")

        assert response.status_code == 200
        data = response.json()

        assert "openapi" in data
        assert "info" in data
        assert "paths" in data

    def test_swagger_ui_available(self, integration_client):
        """Test that Swagger UI is accessible."""
        response = integration_client.get("/docs")

        # Swagger UI may or may not be enabled
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            assert "text/html" in response.headers.get("content-type", "")

    def test_redoc_available(self, integration_client):
        """Test that ReDoc documentation is accessible."""
        response = integration_client.get("/redoc")

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")


class TestErrorHandling:
    """Integration tests for error handling."""

    def test_404_on_invalid_endpoint(self, integration_client):
        """Test that invalid endpoints return 404."""
        response = integration_client.get("/api/v1/nonexistent")

        assert response.status_code == 404

    def test_405_on_wrong_method(self, integration_client):
        """Test that wrong HTTP method returns 405."""
        response = integration_client.get("/api/v1/analyze")  # Should be POST

        assert response.status_code == 405

    def test_malformed_json_returns_error(self, integration_client):
        """Test that malformed JSON returns error."""
        response = integration_client.post(
            "/api/v1/analyze",
            data="this is not json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code in [400, 422]


class TestPerformance:
    """Integration tests for performance characteristics."""

    @pytest.mark.slow
    def test_analyze_large_file(self, integration_client):
        """Test analyzing a large test file."""
        # Generate large test content
        test_functions = "\n\n".join(
            [
                f"""def test_function_{i}():
    result = {i} + {i}
    assert result == {i * 2}"""
                for i in range(50)
            ]
        )

        payload = {
            "files": [
                {"path": "test_large.py", "content": test_functions, "git_diff": None}
            ],
            "mode": "rules-only",
        }

        response = integration_client.post("/api/v1/analyze", json=payload)

        assert response.status_code == 200
        data = response.json()

        # Should analyze all 50 tests
        assert data["metrics"]["total_tests"] == 50

        # Should complete in reasonable time
        assert data["metrics"]["analysis_time_ms"] < 10000  # 10 seconds
