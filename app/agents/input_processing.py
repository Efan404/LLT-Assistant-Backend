"""
Input processing agent for validating and sanitizing analysis requests.

This module provides the InputProcessingAgent which performs comprehensive
validation of incoming analysis requests before processing begins.
"""

import logging
from typing import List

from app.agents.base import BaseAgent
from app.agents.context import AgentContext, AgentResult

logger = logging.getLogger(__name__)

# Configuration constants
MAX_FILES = 50
MAX_FILE_SIZE_BYTES = 1024 * 1024  # 1 MB
VALID_MODES = {"rules-only", "llm-only", "hybrid"}


class InputProcessingAgent(BaseAgent):
    """
    Agent responsible for validating and sanitizing input requests.

    This agent performs quality gates on incoming requests to ensure
    they meet all requirements before processing. It validates file
    counts, sizes, modes, and other constraints.
    """

    async def execute(self, context: AgentContext) -> AgentResult:
        """
        Validate and sanitize input request.

        This method performs comprehensive validation on the request,
        checking file limits, sizes, mode validity, and other constraints.

        Args:
            context: Agent context containing request data

        Returns:
            AgentResult with validation status and statistics
        """
        self.logger.info(
            f"Validating input request: {len(context.files)} files, mode={context.mode}"
        )

        errors: List[str] = []
        warnings: List[str] = []

        # Validate mode
        if context.mode not in VALID_MODES:
            errors.append(
                f"Invalid mode '{context.mode}'. "
                f"Expected one of: {', '.join(sorted(VALID_MODES))}"
            )

        # Validate file count
        file_count = len(context.files)
        if file_count == 0:
            errors.append("No files provided for analysis")
        elif file_count > MAX_FILES:
            errors.append(
                f"Too many files ({file_count}). Maximum allowed is {MAX_FILES}"
            )

        # Validate individual files
        oversized_files = []
        empty_files = []

        for file_input in context.files:
            # Check file size
            file_size = len(file_input.content.encode("utf-8"))
            if file_size > MAX_FILE_SIZE_BYTES:
                oversized_files.append(f"{file_input.path} ({file_size / 1024:.1f} KB)")

            # Check for empty files
            if not file_input.content.strip():
                empty_files.append(file_input.path)

        if oversized_files:
            errors.append(
                f"Files exceed size limit of {MAX_FILE_SIZE_BYTES / 1024:.0f} KB: "
                f"{', '.join(oversized_files)}"
            )

        if empty_files:
            warnings.append(
                f"Files with no content will be skipped: {', '.join(empty_files)}"
            )

        # Calculate statistics
        total_size = sum(len(f.content.encode("utf-8")) for f in context.files)
        avg_size = total_size / file_count if file_count > 0 else 0

        data = {
            "file_count": file_count,
            "total_size_bytes": total_size,
            "average_size_bytes": int(avg_size),
            "mode": context.mode,
            "oversized_files": len(oversized_files),
            "empty_files": len(empty_files),
        }

        success = len(errors) == 0

        if success:
            self.logger.info(
                f"Input validation passed: {file_count} files, "
                f"{total_size / 1024:.1f} KB total"
            )
        else:
            self.logger.error(f"Input validation failed: {errors}")

        return AgentResult(
            success=success,
            data=data,
            errors=errors,
            warnings=warnings,
            metadata={
                "agent": self.name,
                "stage": "input_validation",
                "critical": True,  # Input validation failures are critical
            },
            execution_time_ms=0,  # Will be set by base agent
        )

    async def validate_input(self, context: AgentContext) -> List[str]:
        """
        Validate that basic context requirements are met.

        Args:
            context: Agent context to validate

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        if not hasattr(context, "files"):
            errors.append("Context missing 'files' attribute")

        if not hasattr(context, "mode"):
            errors.append("Context missing 'mode' attribute")

        return errors

    async def validate_output(
        self, result: AgentResult, context: AgentContext
    ) -> List[str]:
        """
        Validate output from input processing.

        Args:
            result: Result from execute()
            context: Agent context for reference

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Ensure data contains expected fields
        if result.data:
            expected_fields = {"file_count", "total_size_bytes", "mode"}
            missing_fields = expected_fields - set(result.data.keys())
            if missing_fields:
                errors.append(
                    f"Result data missing fields: {', '.join(missing_fields)}"
                )

        return errors
