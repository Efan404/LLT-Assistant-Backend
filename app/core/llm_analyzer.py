"""LLM-based analyzer for test code quality issues."""

import json
import logging
from typing import List, Optional, Tuple

from app.analyzers.ast_parser import ParsedTestFile, TestFunctionInfo
from app.api.v1.schemas import Issue, IssueSuggestion
from app.core.llm_client import LLMClient, create_llm_client

logger = logging.getLogger(__name__)

# System prompts for different analysis types

MERGEABILITY_SYSTEM_PROMPT = """
You are an expert Python pytest analyzer specializing in test code quality.
Your task is to analyze test functions and determine if they can be merged
while maintaining clarity and following the single responsibility principle.

Respond ONLY with valid JSON in this format:
{
  "mergeable": true/false,
  "confidence": 0.0-1.0,
  "reason": "explanation of why tests can/cannot be merged",
  "merged_test_name": "suggested name if mergeable",
  "concerns": ["any potential issues with merging"]
}
"""

ASSERTION_QUALITY_SYSTEM_PROMPT = """
You are a pytest testing expert. Analyze test assertions to determine if they
adequately verify the expected behavior. Identify weak, missing, or redundant
assertions.

Respond ONLY with valid JSON in this format:
{
  "issues": [
    {
      "type": "weak-assertion" | "missing-assertion" | "over-assertion",
      "line": <line_number>,
      "severity": "error" | "warning" | "info",
      "message": "description of the issue",
      "suggestion": "how to improve the assertion",
      "example_code": "suggested code fix"
    }
  ],
  "overall_quality": "poor" | "fair" | "good" | "excellent",
  "confidence": 0.0-1.0
}
"""

TEST_SMELL_SYSTEM_PROMPT = """
You are a senior test engineer. Identify code smells in pytest test code that
could lead to flaky tests, maintenance issues, or false positives/negatives.

Respond ONLY with valid JSON in this format:
{
  "smells": [
    {
      "type": "test-smell-category",
      "line": <line_number>,
      "severity": "error" | "warning" | "info",
      "description": "what the smell is",
      "impact": "why this is problematic",
      "suggestion": "how to fix it",
      "example_code": "improved code"
    }
  ],
  "confidence": 0.0-1.0
}

Common test smells to detect:
- time.sleep() usage (flaky timing)
- Global state modification
- Test order dependencies
- Over-mocking (too many @patch decorators)
- Hard-coded credentials or URLs
- Missing cleanup logic
"""

# User prompt templates

MERGEABILITY_USER_PROMPT = """
Analyze if these test functions can be merged:
```python
{test_function_1_code}
```
```python
{test_function_2_code}
```

Context:
- Both tests are in the same test class: {class_name}
- They test the same module: {module_name}
- Current test file has {total_tests} test functions

Consider:
1. Do they test the same behavior/feature?
2. Would merging reduce clarity or violate single responsibility?
3. Are there setup/teardown dependencies?
"""

ASSERTION_QUALITY_USER_PROMPT = """
Analyze the assertion quality in this test function:
```python
{test_function_code}
```

Function being tested:
```python
{implementation_code}  # If available
```

Evaluate:
1. Are assertions testing the right things?
2. Are there missing edge cases?
3. Are assertions too broad (e.g., assert len(x) > 0 instead of assert len(x) == 5)?
4. Are there any redundant assertions?
5. Should exceptions be tested with pytest.raises?

Focus on practical improvements that enhance test reliability.
"""

TEST_SMELL_USER_PROMPT = """
Detect test code smells in this test function:
```python
{test_function_code}
```

Full test class context:
```python
{test_class_code}  # If applicable
```

Pay special attention to:
1. Timing-dependent operations (sleep, polling)
2. External dependencies (network, filesystem, databases)
3. Shared state between tests
4. Complex mock setups that obscure test intent
"""


class LLMAnalyzer:
    """Handles LLM-based analysis of test code."""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.client = llm_client or create_llm_client()

    async def analyze_mergeability(
        self, test1: TestFunctionInfo, test2: TestFunctionInfo, context: ParsedTestFile
    ) -> Optional[Issue]:
        """Check if two tests can be merged."""
        try:
            system_prompt = MERGEABILITY_SYSTEM_PROMPT
            user_prompt = MERGEABILITY_USER_PROMPT.format(
                test_function_1_code=test1.source_code,
                test_function_2_code=test2.source_code,
                class_name=test1.class_name or "module-level",
                module_name=context.file_path,
                total_tests=len(context.test_functions)
                + sum(len(cls.methods) for cls in context.test_classes),
            )

            response = await self.client.chat_completion(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
            )

            result = json.loads(response)

            if result["mergeable"] and result["confidence"] > 0.7:
                suggestion = IssueSuggestion(
                    action="replace",
                    old_code=f"{test1.source_code}\n\n{test2.source_code}",
                    new_code=f"# TODO: Merged test function\n# {result['reason']}",
                    explanation=result["reason"],
                )

                return Issue(
                    file=context.file_path,
                    line=test1.line_number,
                    column=0,
                    severity="info",
                    type="mergeable-tests",
                    message=f"Tests '{test1.name}' and '{test2.name}' could be merged: {result['reason']}",
                    detected_by="llm",
                    suggestion=suggestion,
                )

            return None

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"Error in mergeability analysis: {e}")
            return None

    async def analyze_assertion_quality(
        self,
        test_func: TestFunctionInfo,
        context: ParsedTestFile,
        implementation_code: Optional[str] = None,
    ) -> List[Issue]:
        """Analyze assertion quality in a test function."""
        try:
            system_prompt = ASSERTION_QUALITY_SYSTEM_PROMPT
            user_prompt = ASSERTION_QUALITY_USER_PROMPT.format(
                test_function_code=test_func.source_code,
                implementation_code=implementation_code
                or "# Implementation not available",
            )

            response = await self.client.chat_completion(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
            )

            result = json.loads(response)

            issues = []
            for issue_data in result.get("issues", []):
                if (
                    issue_data["confidence"] > 0.7
                ):  # Only include high-confidence issues
                    suggestion = IssueSuggestion(
                        action="replace",
                        old_code=None,  # Could be extracted from line number
                        new_code=issue_data.get("example_code"),
                        explanation=issue_data["suggestion"],
                    )

                    issues.append(
                        Issue(
                            file=context.file_path,
                            line=test_func.line_number + issue_data["line"] - 1,
                            column=0,
                            severity=issue_data["severity"],
                            type=f"llm-{issue_data['type']}",
                            message=issue_data["message"],
                            detected_by="llm",
                            suggestion=suggestion,
                        )
                    )

            return issues

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            return []
        except Exception as e:
            logger.error(f"Error in assertion quality analysis: {e}")
            return []

    async def analyze_test_smells(
        self,
        test_func: TestFunctionInfo,
        context: ParsedTestFile,
        test_class_code: Optional[str] = None,
    ) -> List[Issue]:
        """Analyze test code smells."""
        try:
            system_prompt = TEST_SMELL_SYSTEM_PROMPT
            user_prompt = TEST_SMELL_USER_PROMPT.format(
                test_function_code=test_func.source_code,
                test_class_code=test_class_code or "# No test class context",
            )

            response = await self.client.chat_completion(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
            )

            result = json.loads(response)

            issues = []
            for smell_data in result.get("smells", []):
                if (
                    smell_data.get("confidence", 1.0) > 0.7
                ):  # Only include high-confidence issues
                    suggestion = IssueSuggestion(
                        action="replace",
                        old_code=None,
                        new_code=smell_data.get("example_code"),
                        explanation=f"{smell_data['description']}. {smell_data['suggestion']}",
                    )

                    issues.append(
                        Issue(
                            file=context.file_path,
                            line=test_func.line_number + smell_data["line"] - 1,
                            column=0,
                            severity=smell_data["severity"],
                            type=f"test-smell-{smell_data['type']}",
                            message=f"Test smell: {smell_data['description']}",
                            detected_by="llm",
                            suggestion=suggestion,
                        )
                    )

            return issues

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            return []
        except Exception as e:
            logger.error(f"Error in test smell analysis: {e}")
            return []

    async def find_similar_tests(
        self, test_functions: List[TestFunctionInfo], context: ParsedTestFile
    ) -> List[Tuple[TestFunctionInfo, TestFunctionInfo]]:
        """Find pairs of test functions that might be mergeable."""
        similar_pairs = []

        # Simple heuristic: tests with similar names in the same class
        for i, test1 in enumerate(test_functions):
            for j, test2 in enumerate(test_functions[i + 1 :], i + 1):
                # Check if tests are in the same class (or both at module level)
                if test1.class_name == test2.class_name:
                    # Check for similar names
                    name1_parts = test1.name.split("_")
                    name2_parts = test2.name.split("_")

                    # If they share most words, they might be similar
                    common_parts = set(name1_parts) & set(name2_parts)
                    if len(common_parts) >= min(len(name1_parts), len(name2_parts)) - 1:
                        similar_pairs.append((test1, test2))

        return similar_pairs

    async def close(self) -> None:
        """Close the LLM client."""
        await self.client.close()
