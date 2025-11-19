"""
Shared context and result structures for agent framework.

This module defines the data structures passed between agents during
the analysis pipeline execution.
"""

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.analyzers.ast_parser import ParsedTestFile
from app.api.v1.schemas import FileInput, Issue


@dataclass
class AgentResult:
    """
    Standardized result returned by agent execution.

    This class represents the output of an agent's execution, including
    success status, data payload, errors, warnings, and metadata.

    Attributes:
        success: Whether the agent execution completed successfully
        data: The main output data from the agent
        errors: List of error messages encountered during execution
        warnings: List of warning messages generated during execution
        metadata: Additional metadata about the execution
        execution_time_ms: Total execution time in milliseconds
    """

    success: bool
    data: Any
    errors: List[str]
    warnings: List[str]
    metadata: Dict[str, Any]
    execution_time_ms: int


@dataclass
class AgentContext:
    """
    Shared context passed between agents in the pipeline.

    This class maintains the state and intermediate results throughout
    the agent pipeline execution. Agents read from and write to this
    context to coordinate their work.

    Attributes:
        request_id: Unique identifier for this analysis request
        files: List of test files to analyze
        mode: Analysis mode (rules-only, llm-only, or hybrid)
        config: Optional configuration overrides

        parsed_files: Parsed AST representations of test files
        rule_issues: Issues detected by rule-based analysis
        llm_issues: Issues detected by LLM-based analysis
        merged_issues: Combined and deduplicated issues

        execution_plan: Strategy determined by planning agent
        agent_results: Results from each agent that has executed
        start_time: Pipeline start timestamp for metrics
    """

    # Request data (immutable after initialization)
    request_id: str
    files: List[FileInput]
    mode: str
    config: Optional[Dict[str, Any]] = None

    # Intermediate results (populated by agents)
    parsed_files: List[ParsedTestFile] = field(default_factory=list)
    rule_issues: List[Issue] = field(default_factory=list)
    llm_issues: List[Issue] = field(default_factory=list)
    merged_issues: List[Issue] = field(default_factory=list)

    # Metadata and tracking
    execution_plan: Dict[str, Any] = field(default_factory=dict)
    agent_results: Dict[str, AgentResult] = field(default_factory=dict)
    start_time: float = field(default_factory=time.time)

    def add_agent_result(self, agent_name: str, result: AgentResult) -> None:
        """
        Record the result of an agent execution.

        Args:
            agent_name: Name of the agent that executed
            result: Result returned by the agent
        """
        self.agent_results[agent_name] = result

    def get_total_execution_time_ms(self) -> int:
        """
        Calculate total pipeline execution time.

        Returns:
            Total execution time in milliseconds since start_time
        """
        return int((time.time() - self.start_time) * 1000)

    def has_errors(self) -> bool:
        """
        Check if any agent has reported errors.

        Returns:
            True if any agent result contains errors
        """
        return any(
            not result.success or result.errors
            for result in self.agent_results.values()
        )

    def get_all_errors(self) -> List[str]:
        """
        Collect all errors from agent results.

        Returns:
            List of all error messages from all agents
        """
        all_errors = []
        for agent_name, result in self.agent_results.items():
            for error in result.errors:
                all_errors.append(f"[{agent_name}] {error}")
        return all_errors

    def get_all_warnings(self) -> List[str]:
        """
        Collect all warnings from agent results.

        Returns:
            List of all warning messages from all agents
        """
        all_warnings = []
        for agent_name, result in self.agent_results.items():
            for warning in result.warnings:
                all_warnings.append(f"[{agent_name}] {warning}")
        return all_warnings

    def get_agent_metrics(self) -> Dict[str, Dict[str, Any]]:
        """
        Extract execution metrics from all agents.

        Returns:
            Dictionary mapping agent names to their execution metrics
        """
        metrics = {}
        for agent_name, result in self.agent_results.items():
            metrics[agent_name] = {
                "success": result.success,
                "execution_time_ms": result.execution_time_ms,
                "error_count": len(result.errors),
                "warning_count": len(result.warnings),
            }
        return metrics
