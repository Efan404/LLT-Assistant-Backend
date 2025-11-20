"""API routes for version 1.

This module defines the REST API endpoints using FastAPI with proper
dependency injection to eliminate global state.
"""

import asyncio
import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status

from app.analyzers.rule_engine import RuleEngine
from app.api.v1.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    GenerateTestsRequest,
    GenerateTestsResponse,
    TaskError,
    TaskStatus as TaskStatusSchema,
)
from app.core.analyzer import TestAnalyzer
from app.core.constants import MAX_FILES_PER_REQUEST
from app.core.llm_analyzer import LLMAnalyzer
from app.core.llm_client import create_llm_client
from app.core.tasks import TaskStatus, create_task, execute_generate_tests_task, get_task

router = APIRouter()
logger = logging.getLogger(__name__)


def get_analyzer() -> TestAnalyzer:
    """
    Dependency injection factory for TestAnalyzer.

    This function follows the Dependency Inversion Principle by creating
    instances with proper dependency injection, eliminating global state.

    Returns:
        TestAnalyzer instance

    Raises:
        HTTPException: If analyzer initialization fails
    """
    try:
        # Initialize components with dependency injection
        rule_engine = RuleEngine()
        llm_client = create_llm_client()
        llm_analyzer = LLMAnalyzer(llm_client)

        # Create main analyzer with injected dependencies
        return TestAnalyzer(rule_engine, llm_analyzer)
    except Exception as e:
        logger.error(f"Failed to initialize analyzer: {e}")
        raise HTTPException(
            status_code=503, detail=f"Failed to initialize analyzer: {str(e)}"
        )


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_tests(
    request: AnalyzeRequest, test_analyzer: TestAnalyzer = Depends(get_analyzer)
) -> AnalyzeResponse:
    """
    Analyze pytest test files for quality issues.

    This endpoint accepts test file content and returns detected issues
    with fix suggestions. Analysis can use rule engine only, LLM only,
    or a hybrid approach.

    Args:
        request: Analysis request containing test files and configuration
        test_analyzer: Injected TestAnalyzer instance

    Returns:
        Analysis response with detected issues and metrics

    Raises:
        HTTPException: If analysis fails or request is invalid
    """
    try:
        # Validate request
        if not request.files:
            raise HTTPException(
                status_code=400, detail="No files provided for analysis"
            )

        if len(request.files) > MAX_FILES_PER_REQUEST:
            raise HTTPException(
                status_code=400,
                detail=f"Too many files (max {MAX_FILES_PER_REQUEST})",
            )

        # Run analysis
        result = await test_analyzer.analyze_files(
            files=request.files, mode=request.mode, config=request.config
        )

        return result

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Analysis failed due to internal error"
        )


@router.get("/health")
async def health_check(
    test_analyzer: TestAnalyzer = Depends(get_analyzer),
) -> Dict[str, Any]:
    """
    Health check endpoint for the API.

    Args:
        test_analyzer: Injected TestAnalyzer instance

    Returns:
        Health status information
    """
    try:
        return {
            "status": "healthy",
            "analyzer_ready": test_analyzer is not None,
            "mode": "full",
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "unhealthy", "error": str(e), "analyzer_ready": False}


@router.get("/modes")
async def get_analysis_modes() -> Dict[str, Any]:
    """
    Get available analysis modes.

    Returns:
        Dictionary containing available analysis modes with descriptions
    """
    from app.core.constants import AnalysisMode

    return {
        "modes": [
            {
                "id": AnalysisMode.RULES_ONLY.value,
                "name": "Rules Only",
                "description": (
                    "Fast analysis using only deterministic rules "
                    "(recommended for quick checks)"
                ),
            },
            {
                "id": AnalysisMode.LLM_ONLY.value,
                "name": "LLM Only",
                "description": (
                    "Deep analysis using only AI (slower but more comprehensive)"
                ),
            },
            {
                "id": AnalysisMode.HYBRID.value,
                "name": "Hybrid",
                "description": (
                    "Combines fast rule-based analysis with AI for "
                    "uncertain cases (recommended)"
                ),
            },
        ]
    }


@router.post(
    "/workflows/generate-tests",
    response_model=GenerateTestsResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_generate_tests(
    request: GenerateTestsRequest,
) -> GenerateTestsResponse:
    """
    Submit a test generation request and return an async task identifier.
    Uses asyncio.create_task to run the generation in the background.
    """
    try:
        task_payload = request.model_dump()
        task_id = await create_task(task_payload)

        # Launch background task using asyncio instead of Celery
        asyncio.create_task(execute_generate_tests_task(task_id, task_payload))

        return GenerateTestsResponse(
            task_id=task_id,
            status=TaskStatus.PENDING.value,
            estimated_duration_seconds=None,
            request_id=task_id,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to submit test generation task: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to submit test generation task",
        ) from exc


@router.get("/tasks/{task_id}", response_model=TaskStatusSchema)
async def get_task_status(task_id: str) -> TaskStatusSchema:
    """
    Get task status and results.

    Poll for async task status and results.
    Used for long-running operations like test generation.

    Args:
        task_id: Task identifier (UUID)

    Returns:
        Task status information

    Raises:
        HTTPException: 404 if task not found
    """
    task_data = await get_task(task_id)
    if task_data is None:
        raise HTTPException(status_code=404, detail="Task not found")

    # Convert task data to TaskStatusSchema
    error = None
    if task_data.get("error"):
        error = TaskError(
            message=task_data["error"],
            details=None,
        )

    return TaskStatusSchema(
        task_id=task_data["id"],
        status=task_data["status"],
        result=task_data.get("result"),
        error=error,
        created_at=task_data.get("created_at"),
        updated_at=task_data.get("updated_at"),
    )
