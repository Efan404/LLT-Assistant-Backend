"""Pydantic models for API v1."""

from typing import Any, Dict, List, Literal, Optional, Union

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


# ============================================================================
# Feature 1: Test Generation (OpenAPI compliant schemas)
# ============================================================================


class GenerateTestsContext(BaseModel):
    """Context for test generation, used for regeneration scenarios."""

    mode: Literal["new", "regenerate"] = Field(
        default="new", description="Generation mode"
    )
    target_function: Optional[str] = Field(
        default=None, description="Target function name for regeneration"
    )


class GenerateTestsRequest(BaseModel):
    """Request payload for Feature 1 workflow: generate tests.

    OpenAPI spec compliant schema with flattened structure.
    """

    source_code: str = Field(description="The Python source code to test")
    user_description: Optional[str] = Field(
        default=None, description="Optional hint or requirement from user"
    )
    existing_test_code: Optional[str] = Field(
        default=None,
        description="Optional existing test code (context for regeneration)",
    )
    context: Optional[GenerateTestsContext] = Field(
        default=None,
        description="Extra context if triggered by Feature 3 (Regeneration)",
    )


class AsyncJobResponse(BaseModel):
    """Response after submitting an async job.

    Used for /workflows/generate-tests and /optimization/coverage.
    """

    task_id: str = Field(description="Asynchronous task identifier (UUID)")
    status: Literal["pending", "processing"] = Field(description="Initial task status")
    estimated_time_seconds: Optional[int] = Field(
        default=None, description="Estimated time to completion in seconds"
    )


class GenerateTestsResult(BaseModel):
    """Result structure for completed test generation tasks."""

    generated_code: str = Field(description="The complete generated test file content")
    explanation: str = Field(description="Explanation of what was generated")


class TaskError(BaseModel):
    """Error details for failed tasks."""

    message: str = Field(description="Error message")
    code: Optional[str] = Field(default=None, description="Error code identifier")
    details: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional error details"
    )


class CoverageUncoveredRange(BaseModel):
    """Uncovered code range for coverage optimization."""

    start_line: int = Field(description="Start line number of uncovered range")
    end_line: int = Field(description="End line number of uncovered range")
    type: Literal["line", "branch"] = Field(description="Type of coverage gap")


class CoverageOptimizationRequest(BaseModel):
    """Request payload for Feature 2 workflow: coverage optimization."""

    source_code: str = Field(description="Target source file content")
    existing_test_code: Optional[str] = Field(
        default=None, description="Current test file content"
    )
    uncovered_ranges: List[CoverageUncoveredRange] = Field(
        description="Ranges parsed by Frontend from coverage.xml"
    )
    framework: Literal["pytest", "unittest"] = Field(
        default="pytest", description="Target testing framework"
    )


class CoverageOptimizationTest(BaseModel):
    """Individual recommended test for coverage optimization."""

    test_code: str = Field(description="The code snippet for the new test case")
    target_line: int = Field(
        description="Recommended line number to insert the ghost text"
    )
    scenario_description: str = Field(description="Description of the test scenario")
    expected_coverage_impact: str = Field(description="Expected impact on coverage")


class CoverageOptimizationResult(BaseModel):
    """Result structure for completed coverage optimization tasks."""

    recommended_tests: List[CoverageOptimizationTest] = Field(
        description="List of recommended tests to fill coverage gaps"
    )


class TaskStatusResponse(BaseModel):
    """Task status response for polling endpoints.

    Used for /tasks/{task_id}.
    """

    task_id: str = Field(description="Task identifier (UUID)")
    status: Literal["pending", "processing", "completed", "failed"] = Field(
        description="Current task status"
    )
    created_at: Optional[str] = Field(
        default=None,
        description="Task creation timestamp (ISO 8601 format)",
    )
    result: Optional[
        Union[GenerateTestsResult, CoverageOptimizationResult, Dict[str, Any]]
    ] = Field(
        default=None,
        description="Task result (when status=completed, type depends on workflow)",
    )
    error: Optional[TaskError] = Field(
        default=None, description="Error details (when status=failed)"
    )
