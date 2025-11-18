"""AST parser for Python pytest test files."""

import ast
import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple, Union


@dataclass
class ImportInfo:
    """Information about an import statement."""

    module: str
    name: str
    alias: Optional[str] = None
    line_number: int = 0


@dataclass
class FixtureInfo:
    """Information about a pytest fixture."""

    name: str
    line_number: int
    scope: Optional[str] = None
    params: Optional[List[str]] = None


@dataclass
class AssertionInfo:
    """Information about an assertion statement."""

    line_number: int
    column: int
    assertion_type: str  # e.g., "equality", "membership", "exception"
    operands: List[str]  # Variable names involved
    is_trivial: bool = False  # e.g., assert True
    source_code: str = ""  # Original source code


@dataclass
class TestFunctionInfo:
    """Information about a single test function."""

    name: str
    line_number: int
    decorators: List[str]
    parameters: List[str]  # Function parameters (fixtures)
    assertions: List[AssertionInfo]
    has_docstring: bool
    body_lines: Tuple[int, int]  # Start and end line numbers
    source_code: str = ""  # Original source code
    class_name: Optional[str] = None  # Parent class name if in test class


@dataclass
class TestClassInfo:
    """Information about a test class."""

    name: str
    line_number: int
    methods: List[TestFunctionInfo]
    decorators: List[str]


@dataclass
class ParsedTestFile:
    """Structured representation of a parsed test file."""

    file_path: str
    imports: List[ImportInfo]
    fixtures: List[FixtureInfo]
    test_functions: List[TestFunctionInfo]
    test_classes: List[TestClassInfo]
    has_syntax_errors: bool = False
    syntax_error_message: Optional[str] = None


class TestFileVisitor(ast.NodeVisitor):
    """AST visitor for extracting test-related information."""

    def __init__(self, source_code: str, file_path: str):
        self.source_code = source_code
        self.file_path = file_path
        self.lines = source_code.splitlines()

        # Results
        self.imports: List[ImportInfo] = []
        self.fixtures: List[FixtureInfo] = []
        self.test_functions: List[TestFunctionInfo] = []
        self.test_classes: List[TestClassInfo] = []

        # Current context
        self.current_class: Optional[TestClassInfo] = None

    def visit_Import(self, node: ast.Import) -> None:
        """Visit import statements."""
        for alias in node.names:
            self.imports.append(
                ImportInfo(
                    module="",
                    name=alias.name,
                    alias=alias.asname,
                    line_number=node.lineno,
                )
            )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Visit from-import statements."""
        module = node.module or ""
        for alias in node.names:
            self.imports.append(
                ImportInfo(
                    module=module,
                    name=alias.name,
                    alias=alias.asname,
                    line_number=node.lineno,
                )
            )
        self.generic_visit(node)

    def visit_FunctionDef(
        self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef]
    ) -> None:
        """Visit function definitions."""
        # Check if it's a test function
        is_test_function = self._is_test_function(node)
        is_fixture = self._is_fixture(node)

        if is_fixture:
            self._process_fixture(node)
        elif is_test_function:
            self._process_test_function(node)

        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit async function definitions."""
        self.visit_FunctionDef(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit class definitions."""
        # Check if it's a test class
        if self._is_test_class(node):
            self._process_test_class(node)

        self.generic_visit(node)

        # Reset current class context
        if self.current_class and self.current_class.name == node.name:
            self.current_class = None

    def visit_Assert(self, node: ast.Assert) -> None:
        """Visit assertion statements."""
        # This is called during generic_visit, so we need to check context
        if self.current_class and self.current_class.methods:
            # We're in a test class method
            current_method = self.current_class.methods[-1]
            assertion_info = self._extract_assertion_info(node)
            if assertion_info:
                current_method.assertions.append(assertion_info)
        elif self.test_functions and not self.current_class:
            # We're in a module-level test function
            current_function = self.test_functions[-1]
            assertion_info = self._extract_assertion_info(node)
            if assertion_info:
                current_function.assertions.append(assertion_info)

        self.generic_visit(node)

    def _is_test_function(
        self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef]
    ) -> bool:
        """Check if function is a test function."""
        # Check function name
        if node.name.startswith("test_"):
            return True

        # Check for pytest.mark decorators
        for decorator in node.decorator_list:
            if self._is_pytest_mark_decorator(decorator):
                return True

        return False

    def _is_fixture(self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> bool:
        """Check if function is a pytest fixture."""
        for decorator in node.decorator_list:
            if self._is_pytest_fixture_decorator(decorator):
                return True
        return False

    def _is_pytest_fixture_decorator(self, decorator: ast.expr) -> bool:
        """Check if decorator is a pytest.fixture decorator."""
        if isinstance(decorator, ast.Call):
            if (
                isinstance(decorator.func, ast.Attribute)
                and decorator.func.attr == "fixture"
                and isinstance(decorator.func.value, ast.Name)
                and decorator.func.value.id == "pytest"
            ):
                return True
        elif isinstance(decorator, ast.Attribute):
            if (
                decorator.attr == "fixture"
                and isinstance(decorator.value, ast.Name)
                and decorator.value.id == "pytest"
            ):
                return True
        return False

    def _is_pytest_mark_decorator(self, decorator: ast.expr) -> bool:
        """Check if decorator is a pytest.mark decorator."""
        if isinstance(decorator, ast.Call):
            if (
                isinstance(decorator.func, ast.Attribute)
                and isinstance(decorator.func.value, ast.Attribute)
                and decorator.func.value.attr == "mark"
                and isinstance(decorator.func.value.value, ast.Name)
                and decorator.func.value.value.id == "pytest"
            ):
                return True
        elif isinstance(decorator, ast.Attribute):
            if (
                isinstance(decorator.value, ast.Attribute)
                and decorator.value.attr == "mark"
                and isinstance(decorator.value.value, ast.Name)
                and decorator.value.value.id == "pytest"
            ):
                return True
        return False

    def _is_test_class(self, node: ast.ClassDef) -> bool:
        """Check if class is a test class."""
        # Check class name
        if node.name.startswith("Test"):
            return True

        # Check for pytest markers or inheritance
        # This is a simplified check - could be enhanced
        return False

    def _process_fixture(
        self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef]
    ) -> None:
        """Process a fixture function."""
        # Extract fixture parameters
        params = [arg.arg for arg in node.args.args if arg.arg != "self"]

        # Extract scope from decorator if present
        scope = None
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call):
                if self._is_pytest_fixture_decorator(decorator):
                    # Check for scope parameter
                    for keyword in decorator.keywords:
                        if keyword.arg == "scope":
                            if isinstance(keyword.value, ast.Constant):
                                scope = keyword.value.value
                            elif isinstance(keyword.value, ast.Str):  # Python < 3.8
                                scope = keyword.value.s
                            break
                    break

        self.fixtures.append(
            FixtureInfo(
                name=node.name, line_number=node.lineno, scope=scope, params=params
            )
        )

    def _process_test_function(
        self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef]
    ) -> None:
        """Process a test function."""
        # Extract decorators
        decorators = []
        for decorator in node.decorator_list:
            decorators.append(ast.dump(decorator))

        # Extract parameters
        params = [arg.arg for arg in node.args.args if arg.arg != "self"]

        # Check for docstring
        has_docstring = (
            node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        )

        # Get function body line range
        body_start = node.body[0].lineno if node.body else node.lineno
        body_end = node.body[-1].end_lineno if node.body else node.lineno

        # Get source code
        source_lines = self.lines[node.lineno - 1 : node.end_lineno]
        source_code = "\n".join(source_lines)

        test_function = TestFunctionInfo(
            name=node.name,
            line_number=node.lineno,
            decorators=decorators,
            parameters=params,
            assertions=[],  # Will be populated by visit_Assert
            has_docstring=has_docstring,
            body_lines=(body_start, body_end),
            source_code=source_code,
            class_name=self.current_class.name if self.current_class else None,
        )

        if self.current_class:
            self.current_class.methods.append(test_function)
        else:
            self.test_functions.append(test_function)

    def _process_test_class(self, node: ast.ClassDef) -> None:
        """Process a test class."""
        # Extract decorators
        decorators = []
        for decorator in node.decorator_list:
            decorators.append(ast.dump(decorator))

        test_class = TestClassInfo(
            name=node.name,
            line_number=node.lineno,
            methods=[],  # Will be populated by _process_test_function
            decorators=decorators,
        )

        self.current_class = test_class
        self.test_classes.append(test_class)

    def _extract_assertion_info(self, node: ast.Assert) -> Optional[AssertionInfo]:
        """Extract information from an assertion statement."""
        # Get source code for the assertion
        assertion_lines = self.lines[node.lineno - 1 : node.end_lineno]
        source_code = "\n".join(assertion_lines)

        # Determine assertion type
        assertion_type = self._get_assertion_type(node.test)

        # Extract operands
        operands = self._extract_operands(node.test)

        # Check if assertion is trivial
        is_trivial = self._is_trivial_assertion(node.test)

        return AssertionInfo(
            line_number=node.lineno,
            column=node.col_offset,
            assertion_type=assertion_type,
            operands=operands,
            is_trivial=is_trivial,
            source_code=source_code,
        )

    def _get_assertion_type(self, test_node: ast.expr) -> str:
        """Determine the type of assertion."""
        if isinstance(test_node, ast.Compare):
            if len(test_node.ops) == 1:
                op = test_node.ops[0]
                if isinstance(op, ast.Eq):
                    return "equality"
                elif isinstance(op, ast.NotEq):
                    return "inequality"
                elif isinstance(op, ast.In):
                    return "membership"
                elif isinstance(op, ast.NotIn):
                    return "non-membership"
                elif isinstance(op, ast.Is):
                    return "identity"
                elif isinstance(op, ast.IsNot):
                    return "non-identity"
                elif isinstance(op, ast.Lt):
                    return "less-than"
                elif isinstance(op, ast.LtE):
                    return "less-than-equal"
                elif isinstance(op, ast.Gt):
                    return "greater-than"
                elif isinstance(op, ast.GtE):
                    return "greater-than-equal"
        elif isinstance(test_node, ast.Call):
            if (
                isinstance(test_node.func, ast.Name)
                and test_node.func.id == "isinstance"
            ):
                return "type-check"
        elif isinstance(test_node, ast.Constant) and test_node.value is True:
            return "trivial-true"

        return "other"

    def _extract_operands(self, test_node: ast.expr) -> List[str]:
        """Extract variable names from assertion operands."""
        operands = []

        if isinstance(test_node, ast.Compare):
            # Extract left operand
            if isinstance(test_node.left, ast.Name):
                operands.append(test_node.left.id)
            elif isinstance(test_node.left, ast.Attribute):
                operands.append(self._get_attribute_name(test_node.left))

            # Extract comparators
            for comparator in test_node.comparators:
                if isinstance(comparator, ast.Name):
                    operands.append(comparator.id)
                elif isinstance(comparator, ast.Attribute):
                    operands.append(self._get_attribute_name(comparator))
                elif isinstance(comparator, ast.Constant):
                    operands.append(str(comparator.value))

        elif isinstance(test_node, ast.Name):
            operands.append(test_node.id)

        return operands

    def _get_attribute_name(self, node: ast.Attribute) -> str:
        """Get full attribute name (e.g., 'obj.attr')."""
        if isinstance(node.value, ast.Name):
            return f"{node.value.id}.{node.attr}"
        elif isinstance(node.value, ast.Attribute):
            return f"{self._get_attribute_name(node.value)}.{node.attr}"
        return node.attr

    def _is_trivial_assertion(self, test_node: ast.expr) -> bool:
        """Check if assertion is trivial (always true)."""
        if isinstance(test_node, ast.Constant):
            return test_node.value is True

        if isinstance(test_node, ast.Compare):
            # Check for patterns like 1 == 1, "x" == "x"
            if len(test_node.comparators) == 1 and isinstance(test_node.ops[0], ast.Eq):
                left = test_node.left
                right = test_node.comparators[0]

                # Both are constants with same value
                if (
                    isinstance(left, ast.Constant)
                    and isinstance(right, ast.Constant)
                    and left.value == right.value
                ):
                    return True

        return False


def parse_test_file(file_path: str, source_code: str) -> ParsedTestFile:
    """
    Parse a Python test file and extract test-related information.

    Args:
        file_path: Path to the file (for reference)
        source_code: Content of the Python file

    Returns:
        ParsedTestFile with extracted information

    Raises:
        SyntaxError: If the source code has syntax errors
    """
    try:
        # Parse the AST
        tree = ast.parse(source_code, filename=file_path)

        # Create visitor and extract information
        visitor = TestFileVisitor(source_code, file_path)
        visitor.visit(tree)

        return ParsedTestFile(
            file_path=file_path,
            imports=visitor.imports,
            fixtures=visitor.fixtures,
            test_functions=visitor.test_functions,
            test_classes=visitor.test_classes,
            has_syntax_errors=False,
        )

    except SyntaxError as e:
        return ParsedTestFile(
            file_path=file_path,
            imports=[],
            fixtures=[],
            test_functions=[],
            test_classes=[],
            has_syntax_errors=True,
            syntax_error_message=str(e),
        )
