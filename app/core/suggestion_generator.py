"""Fix suggestion generator for detected issues."""

import re
from typing import Optional

from app.analyzers.ast_parser import ParsedTestFile, TestFunctionInfo
from app.api.v1.schemas import Issue, IssueSuggestion


class SuggestionGenerator:
    """Generates fix suggestions for detected issues."""

    def generate_for_rule_issue(
        self, issue: Issue, parsed_file: ParsedTestFile
    ) -> IssueSuggestion:
        """Generate deterministic fix for rule engine issues."""

        if issue.type == "redundant-assertion":
            return self._generate_redundant_assertion_suggestion(issue)
        elif issue.type == "missing-assertion":
            return self._generate_missing_assertion_suggestion(issue, parsed_file)
        elif issue.type == "trivial-assertion":
            return self._generate_trivial_assertion_suggestion(issue)
        elif issue.type == "unused-fixture":
            return self._generate_unused_fixture_suggestion(issue)
        elif issue.type == "unused-variable":
            return self._generate_unused_variable_suggestion(issue)
        else:
            # Default suggestion
            return IssueSuggestion(
                action="review",
                old_code=None,
                new_code=None,
                explanation=f"Review and fix the {issue.type} issue.",
            )

    def _generate_redundant_assertion_suggestion(self, issue: Issue) -> IssueSuggestion:
        """Generate suggestion for redundant assertion."""
        # Extract the line content from the issue message if available
        old_code = self._extract_code_from_message(issue)

        return IssueSuggestion(
            action="remove",
            old_code=old_code or "    assert something == expected",
            new_code=None,
            explanation="Remove this duplicate assertion to reduce redundancy. Keep only the first occurrence.",
        )

    def _generate_missing_assertion_suggestion(
        self, issue: Issue, parsed_file: ParsedTestFile
    ) -> IssueSuggestion:
        """Generate suggestion for missing assertion."""
        # Try to find the test function to provide context-aware suggestion
        test_func = self._find_test_function_by_line(issue.line, parsed_file)

        if test_func:
            # Generate context-aware suggestion
            if "create" in test_func.name.lower() or "init" in test_func.name.lower():
                new_code = "    assert created_object is not None\n    assert created_object.property == expected_value"
                explanation = "Add assertions to verify that the object was created successfully and has expected properties."
            elif (
                "calculate" in test_func.name.lower()
                or "compute" in test_func.name.lower()
            ):
                new_code = "    assert result == expected_result\n    assert isinstance(result, expected_type)"
                explanation = (
                    "Add assertions to verify the calculation result and its type."
                )
            elif (
                "exception" in test_func.name.lower()
                or "error" in test_func.name.lower()
            ):
                new_code = "    with pytest.raises(ExpectedException):\n        function_that_should_fail()"
                explanation = (
                    "Use pytest.raises() to test that the expected exception is raised."
                )
            else:
                new_code = "    assert actual_result == expected_result"
                explanation = (
                    "Add assertions to verify the expected behavior of your test."
                )
        else:
            new_code = "    assert result is not None  # Add appropriate assertion"
            explanation = "Add assertions to verify the expected behavior of your test."

        return IssueSuggestion(
            action="add", old_code=None, new_code=new_code, explanation=explanation
        )

    def _generate_trivial_assertion_suggestion(self, issue: Issue) -> IssueSuggestion:
        """Generate suggestion for trivial assertion."""
        old_code = self._extract_code_from_message(issue)

        # Provide specific replacement based on the trivial assertion
        if old_code and "assert True" in old_code:
            new_code = "    assert actual_condition  # Replace with real condition"
            explanation = "Replace 'assert True' with a meaningful assertion that tests actual behavior."
        elif old_code and "==" in old_code:
            new_code = "    assert actual_variable == expected_value"
            explanation = "Replace literal comparison with a meaningful assertion using actual variables."
        else:
            new_code = "    assert actual_result == expected_result"
            explanation = (
                "Replace trivial assertion with a meaningful test of actual behavior."
            )

        return IssueSuggestion(
            action="replace",
            old_code=old_code or "    assert True",
            new_code=new_code,
            explanation=explanation,
        )

    def _generate_unused_fixture_suggestion(self, issue: Issue) -> IssueSuggestion:
        """Generate suggestion for unused fixture."""
        # Extract fixture name from message
        fixture_name = self._extract_fixture_name_from_message(issue)

        old_code = f"@pytest.fixture\ndef {fixture_name or 'fixture_name'}():\n    # fixture implementation"

        return IssueSuggestion(
            action="remove",
            old_code=old_code,
            new_code=None,
            explanation=f"Remove unused fixture '{fixture_name or 'fixture_name'}' to reduce code complexity. If needed later, it can be re-added.",
        )

    def _generate_unused_variable_suggestion(self, issue: Issue) -> IssueSuggestion:
        """Generate suggestion for unused variable."""
        # Extract variable name from message
        var_name = self._extract_variable_name_from_message(issue)

        old_code = f"    {var_name or 'variable_name'} = "  # This is a simplified representation

        return IssueSuggestion(
            action="remove",
            old_code=old_code,
            new_code=None,
            explanation=f"Remove unused variable '{var_name or 'variable_name'}' to reduce code complexity and improve readability.",
        )

    def enhance_llm_suggestion(
        self, issue: Issue, parsed_file: ParsedTestFile
    ) -> IssueSuggestion:
        """Enhance LLM-generated suggestions with better formatting."""

        # If the suggestion already has code examples, keep them
        if issue.suggestion.old_code or issue.suggestion.new_code:
            return issue.suggestion

        # Try to extract code context for better suggestions
        enhanced_suggestion = self._add_code_context(issue, parsed_file)

        if enhanced_suggestion:
            return enhanced_suggestion

        # Return original if we can't enhance it
        return issue.suggestion

    def _add_code_context(
        self, issue: Issue, parsed_file: ParsedTestFile
    ) -> Optional[IssueSuggestion]:
        """Add code context to suggestions when possible."""
        # Find the relevant test function
        test_func = self._find_test_function_by_line(issue.line, parsed_file)

        if not test_func:
            return None

        # Extract the actual line of code
        try:
            lines = test_func.source_code.split("\n")
            line_index = issue.line - test_func.line_number

            if 0 <= line_index < len(lines):
                old_code = lines[line_index].strip()

                # Create enhanced suggestion
                return IssueSuggestion(
                    action=issue.suggestion.action,
                    old_code=old_code,
                    new_code=issue.suggestion.new_code,
                    explanation=issue.suggestion.explanation,
                )
        except (IndexError, AttributeError):
            pass

        return None

    def _find_test_function_by_line(
        self, line_number: int, parsed_file: ParsedTestFile
    ) -> Optional[TestFunctionInfo]:
        """Find the test function that contains the given line."""
        # Check module-level functions
        for test_func in parsed_file.test_functions:
            start_line = test_func.line_number
            end_line = (
                test_func.body_lines[1] if test_func.body_lines[1] else start_line + 50
            )  # Estimate

            if start_line <= line_number <= end_line:
                return test_func

        # Check test class methods
        for test_class in parsed_file.test_classes:
            for test_method in test_class.methods:
                start_line = test_method.line_number
                end_line = (
                    test_method.body_lines[1]
                    if test_method.body_lines[1]
                    else start_line + 50
                )  # Estimate

                if start_line <= line_number <= end_line:
                    return test_method

        return None

    def _extract_code_from_message(self, issue: Issue) -> Optional[str]:
        """Extract code snippet from issue message."""
        # Look for code patterns in the message
        message = issue.message

        # Try to extract assertion patterns
        assertion_match = re.search(r"assert\s+.+", message)
        if assertion_match:
            return f"    {assertion_match.group(0)}"

        # Default pattern
        return None

    def _extract_fixture_name_from_message(self, issue: Issue) -> Optional[str]:
        """Extract fixture name from issue message."""
        message = issue.message

        # Look for pattern "Fixture 'name' is defined"
        match = re.search(r"Fixture\s+'([^']+)'", message)
        if match:
            return match.group(1)

        return None

    def _extract_variable_name_from_message(self, issue: Issue) -> Optional[str]:
        """Extract variable name from issue message."""
        message = issue.message

        # Look for pattern "Variable 'name' is assigned"
        match = re.search(r"Variable\s+'([^']+)'", message)
        if match:
            return match.group(1)

        return None

    def validate_suggestion_syntax(
        self, suggestion: IssueSuggestion, file_content: str
    ) -> bool:
        """
        Validate that a suggestion would produce syntactically valid Python.

        This is a basic check - it doesn't guarantee semantic correctness.
        """
        if not suggestion.new_code:
            return True  # Removal is always syntactically valid

        try:
            # Try to parse the new code
            import ast

            ast.parse(suggestion.new_code.strip())
            return True
        except SyntaxError:
            return False
