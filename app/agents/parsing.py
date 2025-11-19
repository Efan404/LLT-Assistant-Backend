"""
Parsing agent for converting test files to AST representation.

This module provides the ParsingAgent which handles parallel parsing
of test files into structured AST representations using the existing
AST parser.
"""

import asyncio
import logging
from typing import List

from app.agents.base import BaseAgent
from app.agents.context import AgentContext, AgentResult
from app.analyzers.ast_parser import ParsedTestFile, parse_test_file
from app.api.v1.schemas import FileInput

logger = logging.getLogger(__name__)


class ParsingAgent(BaseAgent):
    """
    Agent responsible for parsing test files into AST structures.

    This agent takes raw file inputs and converts them to ParsedTestFile
    objects using the AST parser. It handles syntax errors gracefully
    and processes multiple files in parallel for performance.
    """

    async def execute(self, context: AgentContext) -> AgentResult:
        """
        Parse all test files in parallel.

        This method processes all files in the context, converting them
        from raw source code to structured ParsedTestFile objects. Files
        with syntax errors are still parsed but marked with error flags.

        Args:
            context: Agent context containing files to parse

        Returns:
            AgentResult with parsing statistics and any errors encountered
        """
        self.logger.info(f"Parsing {len(context.files)} test files")

        # Parse all files in parallel
        tasks = [self._parse_single_file(file_input) for file_input in context.files]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Separate successful parses from errors
        parsed_files: List[ParsedTestFile] = []
        errors: List[str] = []
        warnings: List[str] = []
        syntax_error_count = 0

        for file_input, result in zip(context.files, results):
            if isinstance(result, Exception):
                # Unexpected exception during parsing
                error_msg = f"Failed to parse {file_input.path}: {str(result)}"
                self.logger.error(error_msg)
                errors.append(error_msg)
            elif isinstance(result, ParsedTestFile):
                parsed_files.append(result)

                # Check for syntax errors
                if result.has_syntax_errors:
                    syntax_error_count += 1
                    warning_msg = (
                        f"Syntax error in {file_input.path}: "
                        f"{result.syntax_error_message}"
                    )
                    self.logger.warning(warning_msg)
                    warnings.append(warning_msg)
            else:
                error_msg = (
                    f"Unexpected result type for {file_input.path}: {type(result)}"
                )
                self.logger.error(error_msg)
                errors.append(error_msg)

        # Store parsed files in context
        context.parsed_files = parsed_files

        # Calculate statistics
        total_test_functions = sum(
            len(pf.test_functions) + sum(len(tc.methods) for tc in pf.test_classes)
            for pf in parsed_files
        )

        success = len(errors) == 0
        data = {
            "parsed_count": len(parsed_files),
            "syntax_errors": syntax_error_count,
            "total_test_functions": total_test_functions,
            "total_test_classes": sum(len(pf.test_classes) for pf in parsed_files),
        }

        self.logger.info(
            f"Parsing completed: {len(parsed_files)} files, "
            f"{total_test_functions} test functions, "
            f"{syntax_error_count} syntax errors"
        )

        return AgentResult(
            success=success,
            data=data,
            errors=errors,
            warnings=warnings,
            metadata={
                "agent": self.name,
                "stage": "parsing",
            },
            execution_time_ms=0,  # Will be set by base agent
        )

    async def _parse_single_file(self, file_input: FileInput) -> ParsedTestFile:
        """
        Parse a single file into AST representation.

        This method wraps the synchronous parse_test_file() function
        to run it asynchronously without blocking.

        Args:
            file_input: File input containing path and content

        Returns:
            ParsedTestFile object (may have syntax errors flagged)
        """
        # Run the synchronous parser in a thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, parse_test_file, file_input.path, file_input.content
        )

    async def validate_input(self, context: AgentContext) -> List[str]:
        """
        Validate that files are present in the context.

        Args:
            context: Agent context to validate

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        if not context.files:
            errors.append("No files provided for parsing")

        # Validate that all files have content
        for file_input in context.files:
            if not file_input.content:
                errors.append(f"File {file_input.path} has empty content")

        return errors

    async def validate_output(
        self, result: AgentResult, context: AgentContext
    ) -> List[str]:
        """
        Validate that parsing produced results.

        Args:
            result: Result from execute()
            context: Agent context for reference

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        if result.success and not context.parsed_files:
            errors.append("Parsing succeeded but no parsed files were produced")

        # Check that we parsed all non-error files
        if result.success:
            expected_count = len(context.files)
            actual_count = len(context.parsed_files)
            if actual_count < expected_count:
                errors.append(
                    f"Expected {expected_count} parsed files but got {actual_count}"
                )

        return errors
