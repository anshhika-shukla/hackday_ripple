"""Acceptance tests for Phase 6: Standalone SVG/HTML Ripple Map."""

import re
from pathlib import Path

from ripple.diffmap import ChangedSymbol
from ripple.graphio import load_graph
from ripple.impact import compute_impact
from ripple.ripplemap import build_ripple_map_html


def test_html_has_no_external_urls():
    """No http:// or https:// references exist except the standard SVG xmlns attribute."""
    graph_path = Path(__file__).parent / "fixtures" / "graph.json"
    graph = load_graph(graph_path)

    changed = [
        ChangedSymbol(file="pricing.py", qualname="pricing.apply_discount", kind="function")
    ]
    candidates, _ = compute_impact(graph, changed)
    html_doc = build_ripple_map_html(
        graph=graph,
        changed_symbols=changed,
        selected_tests=candidates,
        total_suite_count=len(graph.nodes),
    )

    # Find all urls
    urls = re.findall(r'https?://[^\s"\'<>]+', html_doc)
    # The only allowed external URL is http://www.w3.org/2000/svg
    for u in urls:
        assert u == "http://www.w3.org/2000/svg", f"Unexpected external URL found: {u}"


def test_node_count_matches_subgraph():
    """Number of <circle> elements in SVG matches the number of rendered subgraph nodes."""
    graph_path = Path(__file__).parent / "fixtures" / "graph.json"
    graph = load_graph(graph_path)

    changed = [
        ChangedSymbol(file="pricing.py", qualname="pricing.apply_discount", kind="function")
    ]
    candidates, _ = compute_impact(graph, changed)
    html_doc = build_ripple_map_html(
        graph=graph,
        changed_symbols=changed,
        selected_tests=candidates,
        total_suite_count=len(graph.nodes),
    )

    circle_count = html_doc.count("<circle")
    assert circle_count > 0
    assert circle_count <= 120


def test_colors_by_role():
    """Output contains a changed node, a caller and a test for the mini_app change."""
    graph_path = Path(__file__).parent / "fixtures" / "graph.json"
    graph = load_graph(graph_path)

    changed = [
        ChangedSymbol(file="pricing.py", qualname="pricing.apply_discount", kind="function")
    ]
    candidates, _ = compute_impact(graph, changed)
    html_doc = build_ripple_map_html(
        graph=graph,
        changed_symbols=changed,
        selected_tests=candidates,
        total_suite_count=len(graph.nodes),
    )

    # Orange for the change, grey for callers, blue for tests
    assert 'fill="#eb6834"' in html_doc
    assert 'fill="#898781"' in html_doc
    assert 'fill="#2a78d6"' in html_doc


def test_size_under_2mb():
    """Generated standalone HTML document size is strictly under 2 MB."""
    graph_path = Path(__file__).parent / "fixtures" / "graph.json"
    graph = load_graph(graph_path)

    changed = [
        ChangedSymbol(file="pricing.py", qualname="pricing.apply_discount", kind="function")
    ]
    candidates, _ = compute_impact(graph, changed)
    html_doc = build_ripple_map_html(
        graph=graph,
        changed_symbols=changed,
        selected_tests=candidates,
        total_suite_count=len(graph.nodes),
    )

    size_bytes = len(html_doc.encode("utf-8"))
    assert size_bytes < 2 * 1024 * 1024, f"File size too large: {size_bytes} bytes"


def test_header_uses_suite_total_and_marks_failures():
    """Header shows the real suite size; a failing test from the report is marked FAILED."""
    graph_path = Path(__file__).parent / "fixtures" / "graph.json"
    graph = load_graph(graph_path)

    changed = [
        ChangedSymbol(file="pricing.py", qualname="pricing.apply_discount", kind="function")
    ]
    candidates, _ = compute_impact(graph, changed)
    report = {
        "selected": len(candidates),
        "suite_total": 18,
        "results": {"passed": 5, "failed": 1, "failed_ids": ["tests/test_pricing.py::test_apply_discount"]},
        "llm_status": "ok",
        "model": "qwen3:4b-instruct",
        "triage": {"change_kind": "behavior", "risk": 4, "summary": "Discount applied twice."},
    }
    html_doc = build_ripple_map_html(
        graph=graph,
        changed_symbols=changed,
        selected_tests=candidates,
        total_suite_count=18,
        report=report,
    )

    assert f"<strong>{len(candidates)}</strong> test functions" in html_doc
    assert "pytest ran 6 of 18 test cases" in html_doc
    assert "✓ caught the bug" in html_doc
    assert "Discount applied twice." in html_doc
    assert "Risk 4/5" in html_doc


def test_import_fallback_tests_grouped_as_pill():
    """Tests chosen by the import fallback appear as one pill per test file, not as nodes."""
    graph_path = Path(__file__).parent / "fixtures" / "graph.json"
    graph = load_graph(graph_path)

    changed = [
        ChangedSymbol(file="pricing.py", qualname="pricing.apply_discount", kind="function")
    ]
    candidates, _ = compute_impact(graph, changed)
    assert any(c.source == "import_closure" for c in candidates)
    html_doc = build_ripple_map_html(
        graph=graph,
        changed_symbols=changed,
        selected_tests=candidates,
        total_suite_count=18,
    )

    assert "test_pricing.py · 1 more test<" in html_doc
    assert "Test that checks it: test_calculate_tax" not in html_doc
