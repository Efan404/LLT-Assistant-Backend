"""
Base agent class for the agent framework.

This module defines the abstract base class that all agents must implement.
It provides the core execution pattern with built-in quality gates, error
handling, and metrics tracking.
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from app.agents.context import AgentContext, AgentResult


class BaseAgent(ABC):
    """
    Abstract base class for all agents in the framework.

    This class defines the standard interface and execution pattern for agents.
    Subclasses must implement the execute() method and optionally override
    validation methods.

    The execution flow is:
    1. Validate input (validate_input)
    2. Execute agent logic (execute)
    3. Validate output (validate_output)
    4. Track metrics and errors

    Attributes:
        name: Unique identifier for this agent
        config: Configuration dictionary for agent behavior
        logger: Logger instance for this agent
        metrics: Execution metrics (count, errors, timing)
    """

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the agent.

        Args:
            name: Unique name for this agent (used in logging and metrics)
            config: Optional configuration overrides
        """
        self.name = name
        self.config = config or {}
        self.logger = logging.getLogger(f"agent.{name}")
        self.metrics: Dict[str, Any] = {
            "executions": 0,
            "errors": 0,
            "total_time_ms": 0,
        }

    async def run(self, context: AgentContext) -> AgentResult:
        """
        Execute the agent with built-in quality gates and error handling.

        This is the main entry point for agent execution. It orchestrates
        validation, execution, error handling, and metrics collection.

        Args:
            context: Shared context containing request data and intermediate results

        Returns:
            AgentResult with success status, data, errors, and metadata
        """
        start_time = time.time()

        try:
            self.logger.debug(f"Agent {self.name} starting execution")

            # Quality Gate 1: Input validation
            validation_errors = await self.validate_input(context)
            if validation_errors:
                self.logger.warning(
                    f"Agent {self.name} input validation failed: {validation_errors}"
                )
                result = AgentResult(
                    success=False,
                    data=None,
                    errors=validation_errors,
                    warnings=[],
                    metadata={"agent": self.name, "stage": "input_validation"},
                    execution_time_ms=0,
                )
                context.add_agent_result(self.name, result)
                self._update_metrics(0, False)
                return result

            # Execute agent-specific logic
            self.logger.debug(f"Agent {self.name} executing main logic")
            result = await self.execute(context)

            # Quality Gate 2: Output validation
            output_errors = await self.validate_output(result, context)
            if output_errors:
                self.logger.warning(
                    f"Agent {self.name} output validation failed: {output_errors}"
                )
                result.errors.extend(output_errors)
                result.success = False

            # Update execution time
            execution_time_ms = int((time.time() - start_time) * 1000)
            result.execution_time_ms = execution_time_ms

            # Update metrics
            self._update_metrics(execution_time_ms, result.success)

            # Store result in context
            context.add_agent_result(self.name, result)

            # Log completion
            if result.success:
                self.logger.info(
                    f"Agent {self.name} completed successfully in {execution_time_ms}ms"
                )
            else:
                self.logger.error(
                    f"Agent {self.name} completed with errors in {execution_time_ms}ms: {result.errors}"
                )

            return result

        except Exception as e:
            # Handle unexpected exceptions
            execution_time_ms = int((time.time() - start_time) * 1000)
            self.logger.exception(f"Agent {self.name} raised unexpected exception: {e}")

            # Update metrics to include this failed execution
            self._update_metrics(execution_time_ms, success=False)

            result = AgentResult(
                success=False,
                data=None,
                errors=[f"Unexpected error: {str(e)}"],
                warnings=[],
                metadata={
                    "agent": self.name,
                    "exception_type": type(e).__name__,
                    "stage": "execution",
                },
                execution_time_ms=execution_time_ms,
            )

            context.add_agent_result(self.name, result)
            return result

    @abstractmethod
    async def execute(self, context: AgentContext) -> AgentResult:
        """
        Execute the agent's main logic.

        This method must be implemented by all agent subclasses. It should
        perform the agent's specific task and return a result.

        Args:
            context: Shared context with request data and intermediate results

        Returns:
            AgentResult with the agent's output

        Raises:
            NotImplementedError: If subclass doesn't implement this method
        """
        raise NotImplementedError(f"Agent {self.name} must implement execute()")

    async def validate_input(self, context: AgentContext) -> List[str]:
        """
        Validate input data before execution.

        Override this method to implement agent-specific input validation.
        Return a list of error messages if validation fails, or an empty
        list if validation succeeds.

        Args:
            context: Shared context to validate

        Returns:
            List of error messages (empty if valid)
        """
        return []

    async def validate_output(
        self, result: AgentResult, context: AgentContext
    ) -> List[str]:
        """
        Validate output data after execution.

        Override this method to implement agent-specific output validation.
        Return a list of error messages if validation fails, or an empty
        list if validation succeeds.

        Args:
            result: Result produced by execute()
            context: Shared context for reference

        Returns:
            List of error messages (empty if valid)
        """
        return []

    def _update_metrics(self, execution_time_ms: int, success: bool) -> None:
        """
        Update agent execution metrics.

        Args:
            execution_time_ms: Execution time in milliseconds
            success: Whether execution was successful
        """
        self.metrics["executions"] += 1
        self.metrics["total_time_ms"] += execution_time_ms
        if not success:
            self.metrics["errors"] += 1

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get current agent metrics.

        Returns:
            Dictionary containing execution statistics
        """
        total_executions = self.metrics["executions"]
        avg_time_ms = (
            round(self.metrics["total_time_ms"] / total_executions)
            if total_executions > 0
            else 0
        )

        return {
            "agent_name": self.name,
            "total_executions": total_executions,
            "total_errors": self.metrics["errors"],
            "success_rate": (
                (total_executions - self.metrics["errors"]) / total_executions
                if total_executions > 0
                else 0.0
            ),
            "average_execution_time_ms": avg_time_ms,
            "total_execution_time_ms": self.metrics["total_time_ms"],
        }

    def reset_metrics(self) -> None:
        """Reset agent metrics to initial state."""
        self.metrics = {
            "executions": 0,
            "errors": 0,
            "total_time_ms": 0,
        }

    def __repr__(self) -> str:
        """String representation of the agent."""
        return f"{self.__class__.__name__}(name='{self.name}')"
