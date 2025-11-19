"""API routes for version 1.

This module defines the REST API endpoints using FastAPI with proper
dependency injection to eliminate global state.
"""

import logging
import uuid
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from app.agents.context import AgentContext
from app.agents.input_processing import InputProcessingAgent
from app.agents.llm_analysis import LLMAnalysisAgent
from app.agents.orchestrator import AgentOrchestrator
from app.agents.parsing import ParsingAgent
from app.agents.rule_analysis import RuleAnalysisAgent
from app.agents.strategy_planning import StrategyPlanningAgent
from app.agents.synthesis import SynthesisAgent
from app.analyzers.rule_engine import RuleEngine
from app.api.v1.schemas import AnalysisMetrics, AnalyzeRequest, AnalyzeResponse
from app.core.analyzer import TestAnalyzer
from app.core.llm_analyzer import LLMAnalyzer
from app.core.llm_client import create_llm_client

router = APIRouter()
logger = logging.getLogger(__name__)


def get_analyzer() -> TestAnalyzer:
    """
    Dependency injection factory for TestAnalyzer (legacy).

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


def create_analysis_orchestrator() -> AgentOrchestrator:
    """
    Create the agent orchestrator for test analysis.

    This factory function builds the complete analysis pipeline using
    the agent framework.

    Returns:
        Configured AgentOrchestrator instance
    """
    orchestrator = AgentOrchestrator(name="test_analysis_pipeline")

    # Sequential pre-processing
    orchestrator.add_sequential_agent(InputProcessingAgent(name="input"))
    orchestrator.add_sequential_agent(StrategyPlanningAgent(name="strategy"))
    orchestrator.add_sequential_agent(ParsingAgent(name="parser"))

    # Parallel analysis
    orchestrator.add_parallel_agent_group(
        [
            RuleAnalysisAgent(name="rules"),
            LLMAnalysisAgent(name="llm"),
        ]
    )

    # Post-processing (as a parallel group of one to run after analysis)
    orchestrator.add_parallel_agent_group([SynthesisAgent(name="synthesis")])

    return orchestrator


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_tests(request: AnalyzeRequest) -> AnalyzeResponse:
    """
    Analyze pytest test files for quality issues using agent framework.

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
        # Create unique analysis ID
        analysis_id = str(uuid.uuid4())

        # Create agent context
        context = AgentContext(
            request_id=analysis_id,
            files=request.files,
            mode=request.mode,
            config=request.config,
        )

        # Create and execute orchestrator
        orchestrator = create_analysis_orchestrator()
        result_context = await orchestrator.execute(context)

        # Check for errors
        if result_context.has_errors():
            errors = result_context.get_all_errors()
            logger.error(f"Analysis failed with errors: {errors}")
            raise HTTPException(
                status_code=400,
                detail=f"Analysis failed: {'; '.join(errors[:3])}",
            )

        # Count total tests
        total_tests = sum(
            len(pf.test_functions) + sum(len(tc.methods) for tc in pf.test_classes)
            for pf in result_context.parsed_files
        )

        # Build response
        return AnalyzeResponse(
            analysis_id=analysis_id,
            issues=result_context.merged_issues,
            metrics=AnalysisMetrics(
                total_tests=total_tests,
                issues_count=len(result_context.merged_issues),
                analysis_time_ms=result_context.get_total_execution_time_ms(),
            ),
        )

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
