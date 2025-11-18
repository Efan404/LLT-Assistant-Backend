"""API routes for version 1."""

import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException

from app.analyzers.rule_engine import RuleEngine
from app.api.v1.schemas import AnalysisMetrics, AnalyzeRequest, AnalyzeResponse, Issue
from app.core.analyzer import TestAnalyzer
from app.core.llm_analyzer import LLMAnalyzer
from app.core.llm_client import create_llm_client
from app.core.suggestion_generator import SuggestionGenerator

router = APIRouter()

# Initialize components
analyzer: Optional[TestAnalyzer] = None
suggestion_generator = SuggestionGenerator()


def get_analyzer() -> TestAnalyzer:
    """Get or create the analyzer instance."""
    global analyzer
    if analyzer is None:
        try:
            # Initialize components
            rule_engine = RuleEngine()
            llm_client = create_llm_client()
            llm_analyzer = LLMAnalyzer(llm_client)

            # Create main analyzer
            analyzer = TestAnalyzer(rule_engine, llm_analyzer)
        except Exception as e:
            raise HTTPException(
                status_code=503, detail=f"Failed to initialize analyzer: {str(e)}"
            )

    return analyzer


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_tests(request: AnalyzeRequest) -> AnalyzeResponse:
    """
    Analyze pytest test files for quality issues.

    This endpoint accepts test file content and returns detected issues
    with fix suggestions. Analysis can use rule engine only, LLM only,
    or a hybrid approach.

    Args:
        request: Analysis request containing test files and configuration

    Returns:
        Analysis response with detected issues and metrics

    Raises:
        HTTPException: If analysis fails or request is invalid
    """
    try:
        # Get analyzer instance
        test_analyzer = get_analyzer()

        # Validate request
        if not request.files:
            raise HTTPException(
                status_code=400, detail="No files provided for analysis"
            )

        if len(request.files) > 50:  # Configurable limit
            raise HTTPException(status_code=400, detail="Too many files (max 50)")

        # Run analysis
        result = await test_analyzer.analyze_files(
            files=request.files, mode=request.mode, config=request.config
        )

        # Enhance suggestions for rule-based issues
        enhanced_issues = []
        for issue in result.issues:
            if issue.detected_by == "rule_engine":
                # Find the parsed file for this issue
                parsed_file = None
                for file_input in request.files:
                    if file_input.path == issue.file:
                        # We don't have the parsed file here, so we'll skip enhancement
                        # In a real implementation, we'd pass the parsed files
                        enhanced_issues.append(issue)
                        break
                else:
                    enhanced_issues.append(issue)
            else:
                enhanced_issues.append(issue)

        # Create response with enhanced issues
        return AnalyzeResponse(
            analysis_id=result.analysis_id,
            issues=enhanced_issues,
            metrics=result.metrics,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Log the error and return generic message
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Analysis failed: {e}")
        raise HTTPException(
            status_code=500, detail="Analysis failed due to internal error"
        )


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint for the API."""
    try:
        # Check if analyzer can be initialized
        test_analyzer = get_analyzer()

        return {
            "status": "healthy",
            "analyzer_ready": test_analyzer is not None,
            "mode": "full",  # Could be extended to check LLM connectivity
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e), "analyzer_ready": False}


@router.get("/modes")
async def get_analysis_modes() -> Dict[str, Any]:
    """Get available analysis modes."""
    return {
        "modes": [
            {
                "id": "rules-only",
                "name": "Rules Only",
                "description": "Fast analysis using only deterministic rules (recommended for quick checks)",
            },
            {
                "id": "llm-only",
                "name": "LLM Only",
                "description": "Deep analysis using only AI (slower but more comprehensive)",
            },
            {
                "id": "hybrid",
                "name": "Hybrid",
                "description": "Combines fast rule-based analysis with AI for uncertain cases (recommended)",
            },
        ]
    }
