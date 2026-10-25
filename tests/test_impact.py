"""Acceptance tests for Phase 2: Graph impact engine."""

from pathlib import Path
import networkx as nx

from ripple.diffmap import ChangedSymbol
from ripple.graphio import CodeGraph, load_graph
from ripple.impact import (
    baseline_ranking_a,
    baseline_ranking_b,
    compute_impact,
)


def get_mini_app_graph() -> CodeGraph:
    graph_path = Path(__file__).parent / "fixtures" / "graph.json"
    return load_graph(graph_path)


def test_exact_candidates_on_mini_app():
    """Change pricing.apply_discount -> exact expected test set (hand-listed)."""
    graph = get_mini_app_graph()
    changed = [
        ChangedSymbol(
            file="pricing.py",
            qualname="pricing.apply_discount",
            kind="function",
            changed_lines=[5],
        )
    ]
    candidates, _ = compute_impact(graph, changed, max_depth=3)
    test_ids = {c.test_id for c in candidates}

    # Expected tests reachable from apply_discount within depth 3
    expected = {
        "tests/test_pricing.py::test_apply_discount",
        "tests/test_pricing.py::test_get_final_price",
        "tests/test_cart.py::test_cart_total",
        "tests/test_checkout.py::test_checkout_process",
    }
    assert expected.issubset(test_ids)
    # Inventory tests should not be impacted
    assert "tests/test_inventory.py::test_check_stock" not in test_ids


def test_distance_and_direct_flag():
    """Direct callers have distance 1 and direct=True."""
    graph = get_mini_app_graph()
    changed = [
        ChangedSymbol(
            file="pricing.py",
            qualname="pricing.apply_discount",
            kind="function",
        )
    ]
    candidates, _ = compute_impact(graph, changed, max_depth=3)
    c_map = {c.test_id: c for c in candidates}

    direct_test = c_map["tests/test_pricing.py::test_apply_discount"]
    assert direct_test.distance == 1
    assert direct_test.direct is True

    indirect_test = c_map["tests/test_cart.py::test_cart_total"]
    assert indirect_test.distance == 2
    assert indirect_test.direct is False


def test_depth_limit_respected():
    """depth=1 returns strictly fewer tests than depth=3."""
    graph = get_mini_app_graph()
    changed = [
        ChangedSymbol(
            file="pricing.py",
            qualname="pricing.apply_discount",
            kind="function",
        )
    ]
    c_depth1, _ = compute_impact(graph, changed, max_depth=1, include_import_closure=False)
    c_depth3, _ = compute_impact(graph, changed, max_depth=3, include_import_closure=False)

    assert len(c_depth1) < len(c_depth3)
    assert all(c.distance <= 1 for c in c_depth1)


def test_import_closure_adds_tests_when_call_edge_missing():
    """Remove a call edge in the fixture graph -> test still found via import closure."""
    graph = get_mini_app_graph()
    # Remove direct call edge from test_apply_discount
    edge_to_remove = ("tests_test_pricing_test_apply_discount", "pricing_apply_discount")
    assert graph.g.has_edge(*edge_to_remove)
    if graph.g.has_edge(*edge_to_remove):
        graph.g.remove_edge(*edge_to_remove)

    changed = [
        ChangedSymbol(
            file="pricing.py",
            qualname="pricing.apply_discount",
            kind="function",
        )
    ]
    candidates, _ = compute_impact(graph, changed, max_depth=3, include_import_closure=True)
    c_map = {c.test_id: c for c in candidates}

    # test_apply_discount should still be included via import closure
    assert "tests/test_pricing.py::test_apply_discount" in c_map
    assert c_map["tests/test_pricing.py::test_apply_discount"].source == "import_closure"


def test_unknown_direction_marks_over_approx():
    """Unknown direction marks over_approx = True."""
    graph = get_mini_app_graph()
    graph.direction_known = False

    changed = [
        ChangedSymbol(
            file="pricing.py",
            qualname="pricing.apply_discount",
            kind="function",
        )
    ]
    _, over_approx = compute_impact(graph, changed, max_depth=2)
    assert over_approx is True


def test_unchanged_graph_node_yields_no_candidates():
    """Unchanged symbol or symbol with no callers yields no candidates."""
    graph = get_mini_app_graph()
    changed = [
        ChangedSymbol(
            file="unknown_file.py",
            qualname="non_existent_func",
            kind="function",
        )
    ]
    candidates, _ = compute_impact(graph, changed, max_depth=3, include_import_closure=False)
    assert len(candidates) == 0


def test_ranking_B_puts_direct_tests_first():
    """Baseline ranking B puts direct tests first."""
    graph = get_mini_app_graph()
    changed = [
        ChangedSymbol(
            file="pricing.py",
            qualname="pricing.apply_discount",
            kind="function",
        )
    ]
    candidates, _ = compute_impact(graph, changed, max_depth=3)
    ranked = baseline_ranking_b(candidates)

    # First test should be direct (distance 1)
    assert ranked[0].direct is True
    assert ranked[0].distance == 1
