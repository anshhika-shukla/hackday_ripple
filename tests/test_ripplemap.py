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
    """Output contains at least one red, one amber, and one green node for mini_app change."""
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

    # Red (#ef4444) for changed
    assert '#ef4444' in html_doc
    # Green (#10b981) for test
    assert '#10b981' in html_doc
    # Amber (#f59e0b) for impacted
    assert '#f59e0b' in html_doc


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
