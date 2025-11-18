"""
Pytest configuration for evaluation tests.

Provides fixtures for loading ground truth data and configuring evaluation tests.
"""

import ast
import json
import os
from pathlib import Path
from typing import Any, Dict, List

import pytest

from app.analyzers.ast_parser import (
    AssertionInfo,
    ImportInfo,
    ParsedTestFile,
    TestFunctionInfo,
)


@pytest.fixture(scope="session")
def evaluation_fixtures_dir() -> Path:
    """Provide path to evaluation fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def ground_truth_mergeability(evaluation_fixtures_dir: Path) -> Dict[str, Any]:
    """Load ground truth dataset for mergeability analysis."""
    fixture_path = evaluation_fixtures_dir / "ground_truth_mergeability.json"
    with open(fixture_path, "r") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def ground_truth_assertion_quality(evaluation_fixtures_dir: Path) -> Dict[str, Any]:
    """Load ground truth dataset for assertion quality analysis."""
    fixture_path = evaluation_fixtures_dir / "ground_truth_assertion_quality.json"
    with open(fixture_path, "r") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def ground_truth_test_smells(evaluation_fixtures_dir: Path) -> Dict[str, Any]:
    """Load ground truth dataset for test smell detection."""
    fixture_path = evaluation_fixtures_dir / "ground_truth_test_smells.json"
    with open(fixture_path, "r") as f:
        return json.load(f)


@pytest.fixture
def llm_analyzer_for_eval():
    """
    Provide LLMAnalyzer instance for evaluation tests.

    Note: This requires LLM_API_KEY to be set in environment.
    Returns a wrapper that provides raw LLM responses for evaluation.
    """
    from app.core.llm_analyzer import LLMAnalyzer

    analyzer = LLMAnalyzer()

    class EvaluationAnalyzerWrapper:
        """Wrapper that returns raw LLM dict responses instead of Issue objects."""

        def __init__(self, analyzer):
            self.analyzer = analyzer

        async def analyze_mergeability(self, test1, test2, context):
            """Return raw mergeability analysis dict."""
            import json

            from app.core.llm_analyzer import (
                MERGEABILITY_SYSTEM_PROMPT,
                MERGEABILITY_USER_PROMPT,
            )

            system_prompt = MERGEABILITY_SYSTEM_PROMPT
            user_prompt = MERGEABILITY_USER_PROMPT.format(
                test_function_1_code=test1.source_code,
                test_function_2_code=test2.source_code,
                class_name=test1.class_name or "module-level",
                module_name=context.file_path,
                total_tests=len(context.test_functions)
                + sum(len(cls.methods) for cls in context.test_classes),
            )

            response = await self.analyzer.client.chat_completion(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
            )

            return json.loads(response)

        async def analyze_assertion_quality(
            self, test_func, context, implementation_code=None
        ):
            """Return raw assertion quality analysis dict."""
            import json

            from app.core.llm_analyzer import (
                ASSERTION_QUALITY_SYSTEM_PROMPT,
                ASSERTION_QUALITY_USER_PROMPT,
            )

            system_prompt = ASSERTION_QUALITY_SYSTEM_PROMPT
            user_prompt = ASSERTION_QUALITY_USER_PROMPT.format(
                test_function_code=test_func.source_code,
                implementation_code=implementation_code
                or "# Implementation not available",
            )

            response = await self.analyzer.client.chat_completion(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
            )

            return json.loads(response)

        async def analyze_test_smells(self, test_func, context, test_class_code=None):
            """Return raw test smell analysis dict."""
            import json

            from app.core.llm_analyzer import (
                TEST_SMELL_SYSTEM_PROMPT,
                TEST_SMELL_USER_PROMPT,
            )

            system_prompt = TEST_SMELL_SYSTEM_PROMPT
            user_prompt = TEST_SMELL_USER_PROMPT.format(
                test_function_code=test_func.source_code,
                test_class_code=test_class_code or "# Not in a test class",
            )

            response = await self.analyzer.client.chat_completion(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
            )

            return json.loads(response)

    yield EvaluationAnalyzerWrapper(analyzer)
    # Cleanup is handled by the analyzer's context manager if needed


@pytest.fixture
def skip_if_no_api_key():
    """Skip test if LLM API key is not available."""
    api_key = os.getenv("LLM_API_KEY")
    if not api_key or os.getenv("SKIP_LLM_TESTS", "").lower() == "true":
        pytest.skip("LLM API key not available or LLM tests are disabled")


@pytest.fixture
def evaluation_sample_size() -> int:
    """
    Number of samples to use for evaluation tests.

    Can be overridden with EVALUATION_SAMPLE_SIZE environment variable.
    Defaults to 10 for faster CI/CD runs.
    """
    return int(os.getenv("EVALUATION_SAMPLE_SIZE", "10"))


def parse_test_code_to_objects(
    test_code: str, file_path: str = "eval_test.py"
) -> tuple[TestFunctionInfo, ParsedTestFile]:
    """
    Parse test code string into TestFunctionInfo and ParsedTestFile objects.

    This helper function is used by evaluation tests to convert ground truth
    test code strings into the proper object types expected by LLMAnalyzer methods.

    Args:
        test_code: Python test function code as a string
        file_path: Virtual file path for the test (default: "eval_test.py")

    Returns:
        Tuple of (TestFunctionInfo, ParsedTestFile) ready for LLM analysis

    Raises:
        SyntaxError: If test code cannot be parsed
        ValueError: If no test function is found in the code
    """
    # Parse the code into an AST
    try:
        tree = ast.parse(test_code)
    except SyntaxError as e:
        raise SyntaxError(f"Failed to parse test code: {e}")

    # Extract test function information
    test_function = None
    imports = []
    lines = test_code.splitlines()

    # Find imports
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(
                    ImportInfo(
                        module="",
                        name=alias.name,
                        alias=alias.asname,
                        line_number=node.lineno,
                    )
                )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports.append(
                    ImportInfo(
                        module=module,
                        name=alias.name,
                        alias=alias.asname,
                        line_number=node.lineno,
                    )
                )

    # Find the test function
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("test_") or any(
                _is_pytest_mark(d) for d in node.decorator_list
            ):
                # Extract decorators
                decorators = [ast.dump(d) for d in node.decorator_list]

                # Extract parameters
                parameters = [arg.arg for arg in node.args.args if arg.arg != "self"]

                # Extract assertions
                assertions = []
                for child in ast.walk(node):
                    if isinstance(child, ast.Assert):
                        assertion_type = _get_assertion_type(child.test)
                        operands = _extract_operands(child.test)
                        is_trivial = _is_trivial_assertion(child.test)

                        assertion_lines = lines[child.lineno - 1 : child.end_lineno]
                        source_code = "\n".join(assertion_lines)

                        assertions.append(
                            AssertionInfo(
                                line_number=child.lineno,
                                column=child.col_offset,
                                assertion_type=assertion_type,
                                operands=operands,
                                is_trivial=is_trivial,
                                source_code=source_code,
                            )
                        )

                # Check for docstring
                has_docstring = (
                    node.body
                    and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, (ast.Constant, ast.Str))
                )

                # Get body lines
                body_start = node.body[0].lineno if node.body else node.lineno
                body_end = node.body[-1].end_lineno if node.body else node.lineno

                # Get source code
                source_lines = lines[node.lineno - 1 : node.end_lineno]
                source_code = "\n".join(source_lines)

                test_function = TestFunctionInfo(
                    name=node.name,
                    line_number=node.lineno,
                    decorators=decorators,
                    parameters=parameters,
                    assertions=assertions,
                    has_docstring=has_docstring,
                    body_lines=(body_start, body_end),
                    source_code=source_code,
                    class_name=None,
                )
                break

    if not test_function:
        raise ValueError("No test function found in provided code")

    # Create ParsedTestFile context
    context = ParsedTestFile(
        file_path=file_path,
        imports=imports,
        fixtures=[],
        test_functions=[test_function],
        test_classes=[],
        has_syntax_errors=False,
        syntax_error_message=None,
    )

    return test_function, context


def _is_pytest_mark(decorator: ast.expr) -> bool:
    """Check if decorator is a pytest.mark decorator."""
    if isinstance(decorator, ast.Call):
        if (
            isinstance(decorator.func, ast.Attribute)
            and isinstance(decorator.func.value, ast.Attribute)
            and decorator.func.value.attr == "mark"
        ):
            return True
    elif isinstance(decorator, ast.Attribute):
        if (
            isinstance(decorator.value, ast.Attribute)
            and decorator.value.attr == "mark"
        ):
            return True
    return False


def _get_assertion_type(test_node: ast.expr) -> str:
    """Determine the type of assertion."""
    if isinstance(test_node, ast.Compare):
        if len(test_node.ops) == 1:
            op = test_node.ops[0]
            if isinstance(op, (ast.Eq, ast.NotEq)):
                return "equality"
            elif isinstance(op, (ast.In, ast.NotIn)):
                return "membership"
            elif isinstance(op, (ast.Lt, ast.LtE, ast.Gt, ast.GtE)):
                return "comparison"
            elif isinstance(op, (ast.Is, ast.IsNot)):
                return "identity"
    elif isinstance(test_node, ast.Call):
        if isinstance(test_node.func, ast.Name):
            if test_node.func.id in ("isinstance", "issubclass"):
                return "type_check"
            elif test_node.func.id in ("callable", "hasattr"):
                return "attribute_check"
    elif isinstance(test_node, ast.UnaryOp):
        if isinstance(test_node.op, ast.Not):
            return "boolean"
    elif isinstance(test_node, ast.BoolOp):
        return "boolean"
    elif isinstance(test_node, ast.Constant):
        return "constant"
    return "other"


def _extract_operands(test_node: ast.expr) -> List[str]:
    """Extract variable names from assertion test expression."""
    operands = []
    for node in ast.walk(test_node):
        if isinstance(node, ast.Name):
            operands.append(node.id)
    return list(set(operands))


def _is_trivial_assertion(test_node: ast.expr) -> bool:
    """Check if assertion is trivial (e.g., assert True)."""
    if isinstance(test_node, ast.Constant):
        if test_node.value is True or test_node.value is False:
            return True
    elif isinstance(test_node, ast.NameConstant):
        if test_node.value is True or test_node.value is False:
            return True
    return False
