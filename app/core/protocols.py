"""Protocol definitions for core components.

This module defines abstract interfaces to enable dependency inversion
and loose coupling between components.
"""

from abc import ABC, abstractmethod
from typing import List, Protocol

from app.analyzers.ast_parser import ParsedTestFile
from app.api.v1.schemas import Issue


class RuleEngineProtocol(Protocol):
    """Protocol for rule-based analysis engines."""

    def analyze(self, parsed_file: ParsedTestFile) -> List[Issue]:
        """
        Analyze a parsed test file and return detected issues.

        Args:
            parsed_file: The parsed test file to analyze

        Returns:
            List of detected issues
        """
        ...


class LLMClientProtocol(Protocol):
    """Protocol for LLM API clients."""

    async def chat_completion(
        self,
        messages: List[dict],
        temperature: float = 0.3,
        max_tokens: int = 2000,
        stream: bool = False,
    ) -> str:
        """
        Send a chat completion request to LLM API.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens in response
            stream: Whether to use streaming mode

        Returns:
            LLM response content as string
        """
        ...

    async def close(self) -> None:
        """Close the client and cleanup resources."""
        ...


class LLMAnalyzerProtocol(Protocol):
    """Protocol for LLM-based code analysis."""

    async def analyze_assertion_quality(
        self, test_func, context: ParsedTestFile
    ) -> List[Issue]:
        """
        Analyze assertion quality in a test function.

        Args:
            test_func: Test function to analyze
            context: Parsed test file context

        Returns:
            List of detected issues
        """
        ...

    async def analyze_test_smells(
        self, test_func, context: ParsedTestFile
    ) -> List[Issue]:
        """
        Analyze test code smells.

        Args:
            test_func: Test function to analyze
            context: Parsed test file context

        Returns:
            List of detected issues
        """
        ...

    async def close(self) -> None:
        """Close the analyzer and cleanup resources."""
        ...


class AnalysisStrategy(ABC):
    """Abstract base class for analysis strategies.

    This enables the Open/Closed Principle by allowing new analysis
    strategies to be added without modifying existing code.
    """

    @abstractmethod
    async def analyze(
        self,
        parsed_files: List[ParsedTestFile],
        rule_engine: RuleEngineProtocol,
        llm_analyzer: LLMAnalyzerProtocol,
    ) -> List[Issue]:
        """
        Execute the analysis strategy.

        Args:
            parsed_files: List of parsed test files
            rule_engine: Rule-based analysis engine
            llm_analyzer: LLM-based analyzer

        Returns:
            List of detected issues
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Get the strategy name."""
        pass
