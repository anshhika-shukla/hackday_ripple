"""Acceptance tests for stretch feature: Missing-test generator."""

from pathlib import Path
from unittest.mock import MagicMock

from ripple.diffmap import ChangedSymbol
from ripple.draft import (
    draft_pytest_code,
    find_uncovered_symbols,
    verify_drafted_test_on_baseline,
)
from ripple.graphio import load_graph
from ripple.llm import OllamaClient


def test_find_uncovered_symbols():
    """Identifies symbols with no direct test coverage in graph."""
    graph_path = Path(__file__).parent / "fixtures" / "graph.json"
    graph = load_graph(graph_path)

    # utils.py::format_currency is called by checkout.process_order, but no direct unit test
    changed = [
        ChangedSymbol(
            file="utils.py",
            qualname="utils.format_currency",
            kind="function",
        ),
        # pricing.apply_discount has test_pricing.py::test_apply_discount (distance 1)
        ChangedSymbol(
            file="pricing.py",
            qualname="pricing.apply_discount",
            kind="function",
        ),
    ]

    uncovered = find_uncovered_symbols(graph, changed)
    qualnames = [s.qualname for s in uncovered]
    assert "utils.format_currency" in qualnames
    assert "pricing.apply_discount" not in qualnames


def test_draft_pytest_syntax_validation():
    """Drafted pytest parses into valid Python AST."""
    client = OllamaClient()
    symbol = ChangedSymbol(
        file="pricing.py",
        qualname="apply_discount",
        kind="function",
        old_src="def apply_discount(p, d): return p * (1-d)",
    )

    code = draft_pytest_code(symbol, client)
    compiled = compile(code, "<test>", "exec")
    assert compiled is not None
    assert "def test_" in code


def test_verify_drafted_test_on_baseline(tmp_path: Path):
    """Passing baseline test returns True; failing test returns False."""
    dummy_repo = tmp_path / "repo"
    dummy_repo.mkdir()
    (dummy_repo / "calc.py").write_text("def mul(a, b): return a * b\n", encoding="utf-8")

    valid_test = "from calc import mul\ndef test_mul_baseline(): assert mul(2, 3) == 6\n"
    invalid_test = "from calc import mul\ndef test_mul_baseline(): assert mul(2, 3) == 999\n"

    assert verify_drafted_test_on_baseline(valid_test, dummy_repo) is True
    assert verify_drafted_test_on_baseline(invalid_test, dummy_repo) is False
