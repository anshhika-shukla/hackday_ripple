"""Acceptance tests for the standalone change-story page (ripple map)."""

import re
from pathlib import Path

from ripple.diffmap import ChangedSymbol
from ripple.graphio import load_graph
from ripple.impact import compute_impact
from ripple.ripplemap import build_ripple_map_html

CHANGED = [ChangedSymbol(file="pricing.py", qualname="pricing.apply_discount", kind="function")]
REPORT = {
    "selected": 6,
    "suite_total": 18,
    "results": {"passed": 5, "failed": 1, "failed_ids": ["tests/test_cart.py::test_cart_total"]},
    "llm_status": "ok",
    "model": "qwen3:4b-instruct",
    "triage": {"change_kind": "behavior", "risk": 4, "summary": "Discount applied twice."},
}


def _page(report=None):
    graph = load_graph(Path(__file__).parent / "fixtures" / "graph.json")
    candidates, _ = compute_impact(graph, CHANGED)
    return candidates, build_ripple_map_html(
        graph=graph, changed_symbols=CHANGED, selected_tests=candidates, total_suite_count=18, report=report
    )


def test_html_has_no_external_urls():
    """The page is fully offline: no http:// or https:// references."""
    _, html_doc = _page(REPORT)
    assert re.findall(r'https?://[^\s"\'<>]+', html_doc) == []


def test_every_test_file_listed():
    """Each test file RIPPLE selected gets a card."""
    candidates, html_doc = _page()
    for file in {c.file for c in candidates}:
        assert f'<div class="fname">{file}</div>' in html_doc


def test_code_that_uses_the_change_is_shown():
    """Callers of apply_discount appear by step distance in the middle column."""
    _, html_doc = _page()
    assert "1 step away" in html_doc
    assert '<span class="chip">get_total</span>' in html_doc


def test_header_uses_suite_total_and_marks_failures():
    """Header states functions vs test cases; the failing test and the AI's read are shown."""
    candidates, html_doc = _page(REPORT)
    assert f"<strong>{len(candidates)}</strong> test functions" in html_doc
    assert "pytest ran 6 of 18 test cases" in html_doc
    assert "test_cart_total</code> failed: this test caught the bug" in html_doc
    assert "Discount applied twice." in html_doc
    assert "Risk 4/5" in html_doc


def test_import_fallback_tests_counted_as_run_to_be_safe():
    """Tests chosen by the import fallback are counted separately from tests found via the code."""
    candidates, html_doc = _page()
    assert any(c.source == "import_closure" for c in candidates)
    assert "1 run to be safe" in html_doc


def test_size_under_2mb():
    """Generated standalone HTML document size is strictly under 2 MB."""
    _, html_doc = _page(REPORT)
    assert len(html_doc.encode("utf-8")) < 2 * 1024 * 1024
