"""Pydantic models for API v1."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class FileInput(BaseModel):
    """Individual test file to analyze."""

    path: str = Field(description="File path relative to project root")
    content: str = Field(description="Full file content")
    git_diff: Optional[str] = Field(
        default=None, description="Optional: only analyze changed lines"
    )


class AnalyzeRequest(BaseModel):
    """Request payload for /api/analyze."""

    files: List[FileInput] = Field(description="List of test files to analyze")
    mode: Literal["rules-only", "llm-only", "hybrid"] = Field(
        default="hybrid", description="Analysis mode"
    )
    config: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional configuration overrides"
    )


class IssueSuggestion(BaseModel):
    """Fix suggestion for an issue."""

    action: Literal["remove", "replace", "add"] = Field(
        description="Type of fix action"
    )
    old_code: Optional[str] = Field(
        default=None, description="Code to be replaced or removed"
    )
    new_code: Optional[str] = Field(
        default=None, description="New code to add or replace with"
    )
    explanation: str = Field(description="Explanation of the fix")


class Issue(BaseModel):
    """Detected test quality issue."""

    file: str = Field(description="File path where issue was detected")
    line: int = Field(description="Line number of the issue")
    column: int = Field(description="Column number of the issue")
    severity: Literal["error", "warning", "info"] = Field(
        description="Issue severity level"
    )
    type: str = Field(
        description="Issue type (e.g., 'redundant-assertion', 'missing-assertion')"
    )
    message: str = Field(description="Human-readable issue description")
    detected_by: Literal["rule_engine", "llm"] = Field(
        description="Detection method used"
    )
    suggestion: Optional[IssueSuggestion] = Field(
        default=None, description="Fix suggestion for the issue"
    )


class AnalysisMetrics(BaseModel):
    """Analysis statistics."""

    total_tests: int = Field(description="Total number of test functions analyzed")
    issues_count: int = Field(description="Total number of issues detected")
    analysis_time_ms: int = Field(description="Analysis time in milliseconds")


class AnalyzeResponse(BaseModel):
    """Response payload for /api/analyze."""

    analysis_id: str = Field(description="Unique analysis identifier")
    issues: List[Issue] = Field(description="List of detected issues")
    metrics: AnalysisMetrics = Field(description="Analysis statistics")


class GitContext(BaseModel):
    """Git metadata associated with submitted code."""

    commit_hash: Optional[str] = Field(
        default=None, description="Git commit hash for the submitted code"
    )
    branch: Optional[str] = Field(
        default=None, description="Git branch for the submitted code"
    )


class CodeMetadata(BaseModel):
    """Additional metadata for submitted code."""

    file_path: Optional[str] = Field(
        default=None, description="File path relative to the project root"
    )
    module_path: Optional[str] = Field(
        default=None, description="Python module path for the file"
    )
    git_context: Optional[GitContext] = Field(
        default=None, description="Associated git metadata"
    )


class CodeSubmission(BaseModel):
    """Standardized code submission payload."""

    code: str = Field(description="Source code content")
    language: Literal["python"] = Field(
        default="python", description="Programming language of the code"
    )
    framework: Literal["pytest", "unittest"] = Field(
        default="pytest", description="Target testing framework"
    )
    metadata: Optional[CodeMetadata] = Field(
        default=None, description="Optional metadata describing the code context"
    )


class ClientMetadata(BaseModel):
    """Metadata describing the client making the request."""

    extension_version: Optional[str] = Field(
        default=None, description="Client extension version"
    )
    vscode_version: Optional[str] = Field(
        default=None, description="VSCode version information"
    )
    platform: Optional[str] = Field(
        default=None, description="Client platform (e.g., darwin-arm64)"
    )
    workspace_hash: Optional[str] = Field(
        default=None, description="Opaque identifier for the workspace"
    )


class GenerateTestsConfig(BaseModel):
    """Optional configuration overrides for test generation."""

    auto_review_before_return: bool = Field(
        default=True, description="Run automated checks before returning results"
    )
    max_test_count: int = Field(
        default=8,
        ge=1,
        le=20,
        description="Maximum number of tests to generate",
    )
    preferred_style: Optional[
        Literal["pytest_parametrize", "pytest_plain", "unittest"]
    ] = Field(
        default=None, description="Preferred output style for generated tests"
    )


class GenerateTestsRequest(BaseModel):
    """Request payload for the Feature 1 workflow."""

    code_submission: CodeSubmission = Field(
        description="Code snippet that requires test generation"
    )
    user_description: str = Field(
        min_length=1,
        max_length=200,
        description="Short natural language description of user expectations",
    )
    config: Optional[GenerateTestsConfig] = Field(
        default=None, description="Optional generation configuration"
    )
    client_metadata: Optional[ClientMetadata] = Field(
        default=None, description="Client metadata for telemetry and debugging"
    )


class GenerateTestsResponse(BaseModel):
    """Response payload after submitting a test generation task."""

    task_id: str = Field(description="Asynchronous task identifier")
    status: Literal["pending", "processing"] = Field(
        default="pending", description="Initial task status"
    )
    request_id: Optional[str] = Field(
        default=None, description="Server-side request identifier for tracing"
    )


class TaskError(BaseModel):
    """Error details for failed tasks."""

    message: str = Field(description="Error message")
    details: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional error details"
    )


class TaskStatus(BaseModel):
    """Task status response schema."""

    task_id: str = Field(description="Task identifier (UUID)")
    status: Literal["pending", "processing", "completed", "failed"] = Field(
        description="Current task status"
    )
    result: Optional[Dict[str, Any]] = Field(
        default=None, description="Task result (when status=completed)"
    )
    error: Optional[TaskError] = Field(
        default=None, description="Error details (when status=failed)"
    )
    created_at: Optional[str] = Field(
        default=None, description="Task creation timestamp (ISO 8601)"
    )
    updated_at: Optional[str] = Field(
        default=None, description="Task last update timestamp (ISO 8601)"
    )
