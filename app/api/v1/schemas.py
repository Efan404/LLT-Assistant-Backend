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


# ============================================================================
# Feature 3: Impact Analysis (OpenAPI compliant schemas)
# ============================================================================


class FileChangeEntry(BaseModel):
    """File change entry within project_context.files_changed."""

    path: str = Field(description="Path to changed file relative to project root")
    change_type: Literal["added", "modified", "removed"] = Field(
        default="modified",
        description="Type of change: added, modified, or removed",
    )


class ProjectImpactContext(BaseModel):
    """Project context containing file changes and related test files for impact analysis."""

    files_changed: List[FileChangeEntry] = Field(
        description="List of files that have changed"
    )
    related_tests: List[str] = Field(
        description="List of test files that may be impacted (optional, can be empty)"
    )


class ImpactItem(BaseModel):
    """Individual impact analysis item."""

    test_path: str = Field(description="Path to potentially impacted test file")
    impact_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Impact score from 0.0 to 1.0"
    )
    severity: Literal["high", "medium", "low", "none"] = Field(
        default="none", description="Impact severity level"
    )
    reasons: Optional[List[str]] = Field(
        default=None, description="List of reasons for the impact assessment"
    )


class ImpactAnalysisRequest(BaseModel):
    """Request payload for /analysis/impact endpoint."""

    project_context: ProjectImpactContext = Field(
        description="Project context with changed files and related tests"
    )


class ImpactAnalysisResponse(BaseModel):
    """Response payload for /analysis/impact endpoint."""

    impacted_tests: List[ImpactItem] = Field(
        description="List of test files that may be impacted by the changes"
    )
    severity: Literal["high", "medium", "low", "none"] = Field(
        default="none", description="Overall impact severity level"
    )
    suggested_action: Literal["run-all-tests", "run-affected-tests", "no-action"] = (
        Field(
            default="no-action",
            description="Suggested action based on impact analysis",
        )
    )


# ============================================================================
# Feature 4: Quality Analysis (Batch)
# ============================================================================


class QualityAnalysisRequest(BaseModel):
    """Request payload for /quality/analyze endpoint."""

    files: List[FileInput] = Field(
        description="List of files to analyze for quality issues"
    )
    mode: Literal["fast", "deep", "hybrid"] = Field(
        default="hybrid",
        description="Analysis mode: fast (rules only), deep (LLM only), or hybrid (recommended)",
    )  # Note: Using same FileInput as other endpoints


class FixSuggestion(BaseModel):
    """Fix suggestion for a quality issue."""

    type: Literal["replace", "delete", "insert"] = Field(
        description="Type of fix action"
    )
    new_text: Optional[str] = Field(default=None, description="The code to apply")
    description: Optional[str] = Field(
        default=None, description='Menu label (e.g., "Fix: Remove redundancy")'
    )


class QualityIssue(BaseModel):
    """Detected quality issue in test code."""

    file_path: str = Field(description="File path where issue was detected")
    line: int = Field(description="1-based line number of the issue")
    column: int = Field(default=0, description="Column number of the issue")
    severity: Literal["error", "warning", "info"] = Field(
        description="Issue severity level"
    )
    code: str = Field(description="Issue code identifier (e.g., 'redundant-assertion')")
    message: str = Field(description="Human-readable issue description")
    detected_by: Literal["rule", "llm"] = Field(description="Detection method used")
    suggestion: Optional[FixSuggestion] = Field(
        default=None, description="Fix suggestion for the issue"
    )


class QualitySummary(BaseModel):
    """Summary statistics for quality analysis."""

    total_files: int = Field(description="Total number of files analyzed")
    total_issues: int = Field(description="Total number of issues detected")
    critical_issues: int = Field(
        description="Number of critical (error severity) issues"
    )


class QualityAnalysisResponse(BaseModel):
    """Response payload for /quality/analyze endpoint."""

    analysis_id: Optional[str] = Field(
        default=None, description="Unique analysis identifier"
    )
    summary: QualitySummary = Field(description="Analysis summary statistics")
    issues: List[QualityIssue] = Field(description="List of detected quality issues")
