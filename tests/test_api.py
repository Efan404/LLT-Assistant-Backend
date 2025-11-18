"""Tests for the API endpoints."""

import pytest
from fastapi.testclient import TestClient

from app.api.v1.schemas import AnalyzeRequest, FileInput
from app.main import app


class TestAPI:
    """Test cases for API endpoints."""

    def setup_method(self):
        """Set up test client."""
        self.client = TestClient(app)

    def test_health_check(self):
        """Test health check endpoint."""
        response = self.client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data

    def test_root_endpoint(self):
        """Test root endpoint."""
        response = self.client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "description" in data

    def test_get_analysis_modes(self):
        """Test getting available analysis modes."""
        response = self.client.get("/api/v1/modes")

        assert response.status_code == 200
        data = response.json()
        assert "modes" in data

        modes = data["modes"]
        assert len(modes) == 3

        mode_ids = [mode["id"] for mode in modes]
        assert "rules-only" in mode_ids
        assert "llm-only" in mode_ids
        assert "hybrid" in mode_ids

    def test_analyze_empty_request(self):
        """Test analyze endpoint with empty request."""
        request_data = {"files": [], "mode": "hybrid"}

        response = self.client.post("/api/v1/analyze", json=request_data)

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data

    def test_analyze_valid_request(self):
        """Test analyze endpoint with valid request."""
        test_code = """
def test_example():
    assert True
"""

        request_data = {
            "files": [{"path": "test_example.py", "content": test_code}],
            "mode": "rules-only",
        }

        response = self.client.post("/api/v1/analyze", json=request_data)

        assert response.status_code == 200
        data = response.json()

        # Check response structure
        assert "analysis_id" in data
        assert "issues" in data
        assert "metrics" in data

        # Check metrics
        metrics = data["metrics"]
        assert "total_tests" in metrics
        assert "issues_count" in metrics
        assert "analysis_time_ms" in metrics

    def test_analyze_invalid_mode(self):
        """Test analyze endpoint with invalid mode."""
        request_data = {
            "files": [{"path": "test.py", "content": "def test(): pass"}],
            "mode": "invalid-mode",
        }

        response = self.client.post("/api/v1/analyze", json=request_data)

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data

    def test_analyze_too_many_files(self):
        """Test analyze endpoint with too many files."""
        files = [
            {"path": f"test_{i}.py", "content": f"def test_{i}(): pass"}
            for i in range(60)  # More than the limit
        ]

        request_data = {"files": files, "mode": "rules-only"}

        response = self.client.post("/api/v1/analyze", json=request_data)

        assert response.status_code == 400
        data = response.json()
        assert "Too many files" in data["detail"]

    def test_cors_headers(self):
        """Test that CORS headers are properly set."""
        response = self.client.get("/health")

        # CORS headers should be present
        assert "access-control-allow-origin" in response.headers

    def test_openapi_docs(self):
        """Test that OpenAPI docs are accessible."""
        response = self.client.get("/docs")

        # Should return the Swagger UI
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_redoc_docs(self):
        """Test that ReDoc docs are accessible."""
        response = self.client.get("/redoc")

        # Should return the ReDoc UI
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
