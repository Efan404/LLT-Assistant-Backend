"""API routes for version 1.

This module defines the REST API endpoints using FastAPI with proper
dependency injection to eliminate global state.
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from app.analyzers.rule_engine import RuleEngine
from app.api.v1.schemas import AnalyzeRequest, AnalyzeResponse
from app.core.analyzer import TestAnalyzer
from app.core.constants import MAX_FILES_PER_REQUEST
from app.core.llm_analyzer import LLMAnalyzer
from app.core.llm_client import create_llm_client

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
