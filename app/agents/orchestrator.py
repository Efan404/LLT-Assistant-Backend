"""
Agent orchestrator for managing pipeline execution.

This module provides the AgentOrchestrator class which coordinates
the execution of multiple agents in a defined pipeline, handling
sequential and parallel execution, error recovery, and metrics collection.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from app.agents.base import BaseAgent
from app.agents.context import AgentContext, AgentResult

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """
    Orchestrates the execution of agents in a pipeline.

    This class manages the lifecycle of multiple agents, coordinating
    their execution in sequential or parallel mode, collecting results,
    and handling errors.

    Attributes:
        sequential_agents: List of agents to run sequentially
        parallel_agent_groups: List of agent groups to run in parallel
        name: Name of this orchestrator instance
    """

    def __init__(
        self,
        name: str = "default_orchestrator",
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the orchestrator.

        Args:
            name: Unique identifier for this orchestrator
            config: Optional configuration overrides
        """
        self.name = name
        self.config = config or {}
        self.logger = logging.getLogger(f"orchestrator.{name}")
        self.sequential_agents: List[BaseAgent] = []
        self.parallel_agent_groups: List[List[BaseAgent]] = []

    def add_sequential_agent(self, agent: BaseAgent) -> "AgentOrchestrator":
        """
        Add an agent to be executed sequentially.

        Sequential agents are executed one after another in the order
        they are added.

        Args:
            agent: Agent to add to sequential pipeline

        Returns:
            Self for method chaining
        """
        self.sequential_agents.append(agent)
        self.logger.debug(f"Added sequential agent: {agent.name}")
        return self

    def add_parallel_agent_group(self, agents: List[BaseAgent]) -> "AgentOrchestrator":
        """
        Add a group of agents to be executed in parallel.

        All agents in a group are executed concurrently. The orchestrator
        waits for all agents in the group to complete before proceeding.

        Args:
            agents: List of agents to execute in parallel

        Returns:
            Self for method chaining
        """
        self.parallel_agent_groups.append(agents)
        agent_names = [a.name for a in agents]
        self.logger.debug(f"Added parallel agent group: {agent_names}")
        return self

    async def execute(self, context: AgentContext) -> AgentContext:
        """
        Execute all agents in the pipeline.

        This method orchestrates the execution of all registered agents,
        running sequential agents in order and parallel groups concurrently.

        Execution flow:
        1. Run all sequential agents in order
        2. For each parallel group, run all agents concurrently
        3. Check for critical errors after each stage
        4. Return updated context with all results

        Args:
            context: Shared context to pass through pipeline

        Returns:
            Updated context with results from all agents

        Raises:
            Exception: If a critical error occurs during execution
        """
        self.logger.info(
            f"Starting pipeline execution for request {context.request_id}"
        )

        try:
            # Execute sequential agents
            for agent in self.sequential_agents:
                self.logger.info(f"Executing sequential agent: {agent.name}")
                result = await agent.run(context)

                # Check for critical errors
                if not result.success and self._is_critical_error(result, agent):
                    self.logger.error(
                        f"Critical error in agent {agent.name}, stopping pipeline"
                    )
                    return context

            # Execute parallel agent groups
            for group_idx, agent_group in enumerate(self.parallel_agent_groups):
                self.logger.info(
                    f"Executing parallel agent group {group_idx + 1} "
                    f"with {len(agent_group)} agents"
                )
                results = await self._execute_parallel_group(agent_group, context)

                # Check for critical errors in parallel results
                for agent, result in zip(agent_group, results):
                    if not result.success and self._is_critical_error(result, agent):
                        self.logger.error(
                            f"Critical error in parallel agent {agent.name}, "
                            f"stopping pipeline"
                        )
                        return context

            self.logger.info(
                f"Pipeline execution completed for request {context.request_id} "
                f"in {context.get_total_execution_time_ms()}ms"
            )
            return context

        except Exception as e:
            self.logger.exception(f"Pipeline execution failed: {e}")
            raise

    async def _execute_parallel_group(
        self, agents: List[BaseAgent], context: AgentContext
    ) -> List[AgentResult]:
        """
        Execute a group of agents in parallel.

        All agents in the group are started concurrently and the method
        waits for all to complete.

        Args:
            agents: List of agents to execute in parallel
            context: Shared context to pass to all agents

        Returns:
            List of AgentResults in the same order as input agents
        """
        # Create tasks for all agents
        tasks = [agent.run(context) for agent in agents]

        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to failed AgentResults
        final_results = []
        for agent, result in zip(agents, results):
            if isinstance(result, Exception):
                self.logger.error(
                    f"Agent {agent.name} raised exception in parallel group: {result}"
                )
                final_results.append(
                    AgentResult(
                        success=False,
                        data=None,
                        errors=[f"Exception during execution: {str(result)}"],
                        warnings=[],
                        metadata={
                            "agent": agent.name,
                            "exception_type": type(result).__name__,
                        },
                        execution_time_ms=0,
                    )
                )
            else:
                final_results.append(result)

        return final_results

    def _is_critical_error(self, result: AgentResult, agent: BaseAgent) -> bool:
        """
        Determine if an agent failure should stop the pipeline.

        Override this method to customize error handling behavior.

        Args:
            result: Agent execution result
            agent: Agent that produced the result

        Returns:
            True if the pipeline should stop, False otherwise
        """
        # By default, only stop on parsing errors or input validation failures
        if "stage" in result.metadata:
            critical_stages = {"input_validation", "parsing"}
            return result.metadata["stage"] in critical_stages

        # Check for critical error indicators in metadata
        if result.metadata.get("critical", False):
            return True

        return False

    def get_pipeline_summary(self, context: AgentContext) -> Dict[str, Any]:
        """
        Generate a summary of the pipeline execution.

        Args:
            context: Context with agent execution results

        Returns:
            Dictionary containing pipeline metrics and status
        """
        agent_metrics = context.get_agent_metrics()
        all_errors = context.get_all_errors()
        all_warnings = context.get_all_warnings()

        total_execution_time = sum(
            m["execution_time_ms"] for m in agent_metrics.values()
        )
        successful_agents = sum(1 for m in agent_metrics.values() if m["success"])
        total_agents = len(agent_metrics)

        return {
            "orchestrator_name": self.name,
            "request_id": context.request_id,
            "total_execution_time_ms": context.get_total_execution_time_ms(),
            "agent_execution_time_ms": total_execution_time,
            "total_agents": total_agents,
            "successful_agents": successful_agents,
            "failed_agents": total_agents - successful_agents,
            "total_errors": len(all_errors),
            "total_warnings": len(all_warnings),
            "errors": all_errors,
            "warnings": all_warnings,
            "agent_metrics": agent_metrics,
        }

    def reset_all_metrics(self) -> None:
        """Reset metrics for all registered agents."""
        for agent in self.sequential_agents:
            agent.reset_metrics()
        for group in self.parallel_agent_groups:
            for agent in group:
                agent.reset_metrics()
        self.logger.info("All agent metrics reset")

    def __repr__(self) -> str:
        """String representation of the orchestrator."""
        seq_count = len(self.sequential_agents)
        parallel_count = sum(len(group) for group in self.parallel_agent_groups)
        return (
            f"AgentOrchestrator(name='{self.name}', "
            f"sequential_agents={seq_count}, "
            f"parallel_agents={parallel_count})"
        )


class ParallelAgentGroup:
    """
    Utility class for grouping agents for parallel execution.

    This is a convenience wrapper for creating parallel agent groups
    with a more explicit API.
    """

    def __init__(self, name: str, agents: List[BaseAgent]):
        """
        Initialize the parallel agent group.

        Args:
            name: Name for this group (used in logging)
            agents: List of agents to execute in parallel
        """
        self.name = name
        self.agents = agents

    async def run_all(self, context: AgentContext) -> List[AgentResult]:
        """
        Execute all agents in the group concurrently.

        Args:
            context: Shared context for all agents

        Returns:
            List of results from all agents
        """
        tasks = [agent.run(context) for agent in self.agents]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to failed results
        final_results = []
        for agent, result in zip(self.agents, results):
            if isinstance(result, Exception):
                final_results.append(
                    AgentResult(
                        success=False,
                        data=None,
                        errors=[str(result)],
                        warnings=[],
                        metadata={"agent": agent.name},
                        execution_time_ms=0,
                    )
                )
            else:
                final_results.append(result)

        return final_results
