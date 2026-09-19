"""Repository-wide code-size guard.

Issue #53 caps every production class in ``sec_mcp/`` at 300 AST lines and
every function (sync or async, module-level or method) at 50 AST lines,
measured inclusively as ``end_lineno - lineno + 1`` — decorators excluded.
Test files are not part of the production tree and are not scanned.
"""

import ast
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
MAX_CLASS_LINES = 300
MAX_FUNCTION_LINES = 50


def _production_files():
    """Every production ``.py`` file under sec_mcp/, excluding tests/."""
    return sorted(
        path
        for path in PACKAGE_ROOT.rglob("*.py")
        if "tests" not in path.relative_to(PACKAGE_ROOT).parts
    )


def _iter_defs(tree):
    """All class and function definitions in a parsed module."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            yield "class", node
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield "function", node


def _line_span(node) -> int:
    """Inclusive AST line span — the same measure the audit applies."""
    return node.end_lineno - node.lineno + 1


@pytest.mark.parametrize("path", _production_files(), ids=lambda p: p.name)
def test_code_size_limits(path):
    """No class exceeds 300 lines and no function exceeds 50 lines."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations = []
    for kind, node in _iter_defs(tree):
        span = _line_span(node)
        limit = MAX_CLASS_LINES if kind == "class" else MAX_FUNCTION_LINES
        if span > limit:
            violations.append(
                f"{kind} {node.name} (line {node.lineno}): {span} lines > {limit}"
            )
    assert not violations, f"{path.name} exceeds size limits:\n" + "\n".join(violations)
