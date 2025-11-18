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
