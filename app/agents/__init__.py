"""
Agent framework for modular test analysis pipeline.

This package implements a lightweight agent-based architecture for analyzing
pytest test files. Each agent is a self-contained unit with specific responsibilities,
quality gates, and metrics tracking.
"""

from app.agents.base import BaseAgent
from app.agents.context import AgentContext, AgentResult

__all__ = [
    "BaseAgent",
    "AgentContext",
    "AgentResult",
]
