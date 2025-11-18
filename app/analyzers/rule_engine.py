"""Rule engine for detecting test quality issues."""

import ast
from abc import ABC, abstractmethod
from typing import List, Set

from app.analyzers.ast_parser import AssertionInfo, ParsedTestFile, TestFunctionInfo
from app.api.v1.schemas import Issue, IssueSuggestion
from app.core.constants import (
    ACTION_ADD,
    ACTION_REMOVE,
    ACTION_REPLACE,
    DETECTED_BY_RULE_ENGINE,
    ISSUE_TYPE_MISSING_ASSERTION,
    ISSUE_TYPE_REDUNDANT_ASSERTION,
    ISSUE_TYPE_TRIVIAL_ASSERTION,
    ISSUE_TYPE_UNUSED_FIXTURE,
    ISSUE_TYPE_UNUSED_VARIABLE,
    Severity,
)


class Rule(ABC):
    """Base class for detection rules."""

    def __init__(self, rule_id: str, severity: str, message_template: str):
        self.rule_id = rule_id
        self.severity = severity
        self.message_template = message_template

    @abstractmethod
    def check(self, parsed_file: ParsedTestFile) -> List[Issue]:
        """Run the rule and return detected issues."""
        pass

    def create_issue(
        self,
        file_path: str,
        line: int,
        column: int = 0,
        message: str = "",
        suggestion: IssueSuggestion = None,
    ) -> Issue:
        """Create an issue with the rule's default properties."""
        return Issue(
            file=file_path,
            line=line,
            column=column,
            severity=self.severity,
            type=self.rule_id,
            message=message or self.message_template,
            detected_by=DETECTED_BY_RULE_ENGINE,
            suggestion=suggestion
            or IssueSuggestion(
                action=ACTION_REMOVE, explanation="No specific suggestion provided"
            ),
        )


class RedundantAssertionRule(Rule):
    """Detect duplicate assertions within the same test function."""

    def __init__(self):
        super().__init__(
            rule_id=ISSUE_TYPE_REDUNDANT_ASSERTION,
            severity=Severity.WARNING.value,
            message_template="Duplicate assertion found",
        )

    def check(self, parsed_file: ParsedTestFile) -> List[Issue]:
        """Check for redundant assertions in test functions."""
        issues = []

        # Check module-level test functions
        for test_func in parsed_file.test_functions:
            issues.extend(self._check_function(test_func, parsed_file.file_path))

        # Check test class methods
        for test_class in parsed_file.test_classes:
            for test_method in test_class.methods:
                issues.extend(self._check_function(test_method, parsed_file.file_path))

        return issues

    def _check_function(
        self, test_func: TestFunctionInfo, file_path: str
    ) -> List[Issue]:
        """Check a single test function for redundant assertions."""
        issues = []
        seen_assertions = {}

        for assertion in test_func.assertions:
            # Create a canonical representation of the assertion
            assertion_key = self._get_assertion_key(assertion)

            if assertion_key in seen_assertions:
                # Found a duplicate
                original = seen_assertions[assertion_key]
                suggestion = IssueSuggestion(
                    action=ACTION_REMOVE,
                    old_code=assertion.source_code,
                    new_code=None,
                    explanation=(
                        f"This assertion is identical to the one at line "
                        f"{original.line_number}. Remove to reduce redundancy."
                    ),
                )

                issues.append(
                    self.create_issue(
                        file_path=file_path,
                        line=assertion.line_number,
                        column=assertion.column,
                        message=f"Redundant assertion: same as line {original.line_number}",
                        suggestion=suggestion,
                    )
                )
            else:
                seen_assertions[assertion_key] = assertion

        return issues

    def _get_assertion_key(self, assertion: AssertionInfo) -> str:
        """Get a canonical key for comparing assertions."""
        # Remove comments and normalize whitespace for comparison
        # Split on '#' to remove inline comments
        code_without_comment = assertion.source_code.split("#")[0].strip()
        # Normalize whitespace
        normalized = " ".join(code_without_comment.split())
        return normalized


class MissingAssertionRule(Rule):
    """Detect test functions with no assertions."""

    def __init__(self):
        super().__init__(
            rule_id=ISSUE_TYPE_MISSING_ASSERTION,
            severity=Severity.ERROR.value,
            message_template="Test function has no assertions",
        )

    def check(self, parsed_file: ParsedTestFile) -> List[Issue]:
        """Check for test functions without assertions."""
        issues = []

        # Check module-level test functions
        for test_func in parsed_file.test_functions:
            if self._has_no_assertions(test_func):
                issues.append(
                    self._create_missing_assertion_issue(
                        test_func, parsed_file.file_path
                    )
                )

        # Check test class methods
        for test_class in parsed_file.test_classes:
            for test_method in test_class.methods:
                if self._has_no_assertions(test_method):
                    issues.append(
                        self._create_missing_assertion_issue(
                            test_method, parsed_file.file_path
                        )
                    )

        return issues

    def _has_no_assertions(self, test_func: TestFunctionInfo) -> bool:
        """Check if test function has no assertions."""
        # Check for assertions
        if test_func.assertions:
            return False

        # Check for pytest.raises usage (exception testing)
        # This is a simplified check - could be enhanced with AST analysis
        if "pytest.raises" in test_func.source_code:
            return False

        return True

    def _create_missing_assertion_issue(
        self, test_func: TestFunctionInfo, file_path: str
    ) -> Issue:
        """Create an issue for missing assertions."""
        suggestion = IssueSuggestion(
            action=ACTION_ADD,
            old_code=None,
            new_code="    assert result is not None  # Add appropriate assertion",
            explanation="Add assertions to verify the expected behavior of your test.",
        )

        return self.create_issue(
            file_path=file_path,
            line=test_func.line_number,
            message=f"Test function '{test_func.name}' has no assertions",
            suggestion=suggestion,
        )


class TrivialAssertionRule(Rule):
    """Detect trivial assertions that always pass."""

    def __init__(self):
        super().__init__(
            rule_id=ISSUE_TYPE_TRIVIAL_ASSERTION,
            severity=Severity.ERROR.value,
            message_template="Trivial assertion that always passes",
        )

    def check(self, parsed_file: ParsedTestFile) -> List[Issue]:
        """Check for trivial assertions."""
        issues = []

        # Check module-level test functions
        for test_func in parsed_file.test_functions:
            issues.extend(self._check_function(test_func, parsed_file.file_path))

        # Check test class methods
        for test_class in parsed_file.test_classes:
            for test_method in test_class.methods:
                issues.extend(self._check_function(test_method, parsed_file.file_path))

        return issues

    def _check_function(
        self, test_func: TestFunctionInfo, file_path: str
    ) -> List[Issue]:
        """Check a single test function for trivial assertions."""
        issues = []

        for assertion in test_func.assertions:
            if assertion.is_trivial:
                suggestion = IssueSuggestion(
                    action=ACTION_REPLACE,
                    old_code=assertion.source_code,
                    new_code="    assert actual_result == expected_result",
                    explanation="Replace with a meaningful assertion that tests actual behavior.",
                )

                issues.append(
                    self.create_issue(
                        file_path=file_path,
                        line=assertion.line_number,
                        column=assertion.column,
                        message=f"Trivial assertion: {assertion.source_code.strip()}",
                        suggestion=suggestion,
                    )
                )

        return issues


class UnusedFixtureRule(Rule):
    """Detect fixtures that are defined but never used."""

    def __init__(self):
        super().__init__(
            rule_id=ISSUE_TYPE_UNUSED_FIXTURE,
            severity=Severity.INFO.value,
            message_template="Fixture is defined but never used",
        )

    def check(self, parsed_file: ParsedTestFile) -> List[Issue]:
        """Check for unused fixtures."""
        issues = []

        # Build set of used fixtures
        used_fixtures = self._get_used_fixtures(parsed_file)

        # Check each fixture
        for fixture in parsed_file.fixtures:
            if fixture.name not in used_fixtures:
                suggestion = IssueSuggestion(
                    action=ACTION_REMOVE,
                    old_code=(
                        f"@pytest.fixture\ndef {fixture.name}():\n"
                        f"    # fixture implementation"
                    ),
                    new_code=None,
                    explanation="Remove unused fixture to reduce code complexity.",
                )

                issues.append(
                    self.create_issue(
                        file_path=parsed_file.file_path,
                        line=fixture.line_number,
                        message=f"Fixture '{fixture.name}' is defined but never used",
                        suggestion=suggestion,
                    )
                )

        return issues

    def _get_used_fixtures(self, parsed_file: ParsedTestFile) -> Set[str]:
        """Get set of fixture names that are used in test functions."""
        used_fixtures = set()

        # Check module-level test functions
        for test_func in parsed_file.test_functions:
            used_fixtures.update(test_func.parameters)

        # Check test class methods
        for test_class in parsed_file.test_classes:
            for test_method in test_class.methods:
                used_fixtures.update(test_method.parameters)

        return used_fixtures


class UnusedVariableRule(Rule):
    """Detect variables that are defined but never used."""

    def __init__(self):
        super().__init__(
            rule_id=ISSUE_TYPE_UNUSED_VARIABLE,
            severity=Severity.INFO.value,
            message_template="Variable is defined but never used",
        )

    def check(self, parsed_file: ParsedTestFile) -> List[Issue]:
        """Check for unused variables in test functions."""
        issues = []

        # Check module-level test functions
        for test_func in parsed_file.test_functions:
            issues.extend(
                self._check_function_variables(test_func, parsed_file.file_path)
            )

        # Check test class methods
        for test_class in parsed_file.test_classes:
            for test_method in test_class.methods:
                issues.extend(
                    self._check_function_variables(test_method, parsed_file.file_path)
                )

        return issues

    def _check_function_variables(
        self, test_func: TestFunctionInfo, file_path: str
    ) -> List[Issue]:
        """Check for unused variables in a test function."""
        issues = []

        try:
            # Parse the function body
            func_ast = ast.parse(test_func.source_code)
            if not func_ast.body or not isinstance(
                func_ast.body[0], (ast.FunctionDef, ast.AsyncFunctionDef)
            ):
                return issues

            func_node = func_ast.body[0]

            # Find all variable assignments and references
            assigned_vars = set()
            referenced_vars = set()

            for node in ast.walk(func_node):
                # Variable assignments
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id != "_":
                            assigned_vars.add(target.id)
                        elif isinstance(target, ast.Tuple):
                            for elt in target.elts:
                                if isinstance(elt, ast.Name) and elt.id != "_":
                                    assigned_vars.add(elt.id)

                # Variable references
                elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                    referenced_vars.add(node.id)

            # Find unused variables (exclude function parameters)
            unused_vars = assigned_vars - referenced_vars - set(test_func.parameters)

            # Create issues for unused variables
            for var_name in unused_vars:
                # Find the line where the variable is assigned
                line_number = self._find_assignment_line(func_node, var_name)

                suggestion = IssueSuggestion(
                    action=ACTION_REMOVE,
                    old_code=f"    {var_name} = ",  # Simplified - could be more specific
                    new_code=None,
                    explanation=f"Remove unused variable '{var_name}' to reduce code complexity.",
                )

                issues.append(
                    self.create_issue(
                        file_path=file_path,
                        line=test_func.line_number + line_number - 1,
                        message=f"Unused variable '{var_name}' is assigned but never used",
                        suggestion=suggestion,
                    )
                )

        except SyntaxError:
            # Skip functions with syntax errors
            pass

        return issues

    def _find_assignment_line(self, func_node: ast.FunctionDef, var_name: str) -> int:
        """Find the line number where a variable is assigned."""
        for node in ast.walk(func_node):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == var_name:
                        return node.lineno
                    elif isinstance(target, ast.Tuple):
                        for elt in target.elts:
                            if isinstance(elt, ast.Name) and elt.id == var_name:
                                return node.lineno
        return 1  # Default to first line if not found


class RuleEngine:
    """Orchestrates all detection rules."""

    def __init__(self):
        self.rules = [
            RedundantAssertionRule(),
            MissingAssertionRule(),
            TrivialAssertionRule(),
            UnusedFixtureRule(),
            UnusedVariableRule(),
        ]

    def analyze(self, parsed_file: ParsedTestFile) -> List[Issue]:
        """Run all rules and aggregate issues."""
        issues = []
        for rule in self.rules:
            issues.extend(rule.check(parsed_file))
        return issues
