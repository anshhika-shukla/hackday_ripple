"""Acceptance tests for Phase 4: LLM triage, ranking, and guardrails G1-G5."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ripple.diffmap import ChangedSymbol
from ripple.graphio import load_graph
from ripple.llm import OllamaClient, strip_think_blocks
from ripple.triage import (
    Rank,
    Triage,
    rank_candidates,
    select_and_rank_tests,
    triage_change,
)


@pytest.fixture
def mini_graph():
    path = Path(__file__).parent / "fixtures" / "graph.json"
    return load_graph(path)


def test_garbage_json_falls_back_to_graph_ranking(mini_graph):
    """G4: Garbage JSON falls back to graph ranking with status 'fallback'."""
    client = OllamaClient()
    # Mock chat_json to simulate garbage / decode error
    client.chat_json = MagicMock(return_value=(None, "fallback"))

    changed = [
        ChangedSymbol(
            file="pricing.py",
            qualname="pricing.apply_discount",
            kind="function",
            ast_equal=False,
        )
    ]
    selected, triage, guardrails, status = select_and_rank_tests(
        graph=mini_graph,
        changed_symbols=changed,
        diff_text="diff --git a/pricing.py ...",
        client=client,
        mode="safe",
        use_cache=False,
    )
    assert status == "fallback"
    assert "G4" in guardrails
    assert len(selected) > 0


def test_timeout_falls_back(mini_graph):
    """G4: Timeout falls back to graph ranking."""
    client = OllamaClient()
    client.chat_json = MagicMock(return_value=(None, "fallback"))

    changed = [
        ChangedSymbol(
            file="pricing.py",
            qualname="pricing.apply_discount",
            kind="function",
            ast_equal=False,
        )
    ]
    selected, triage, guardrails, status = select_and_rank_tests(
        graph=mini_graph,
        changed_symbols=changed,
        diff_text="timeout test diff",
        client=client,
        mode="safe",
        use_cache=False,
    )
    assert status == "fallback"
    assert "G4" in guardrails


def test_unknown_indices_are_discarded():
    """G3: Unknown candidate indices returned by LLM are safely discarded."""
    client = OllamaClient()
    # LLM returns indices [0, 999, -5, 1] for 2 candidates
    client.chat_json = MagicMock(return_value=(Rank(order=[0, 999, -5, 1]), "ok"))

    candidates = [
        MagicMock(test_id="test_1", via=["via1"], distance=1),
        MagicMock(test_id="test_2", via=["via2"], distance=2),
    ]
    triage = Triage(change_kind="behavior", risk=2, summary="test")
    valid_indices, status = rank_candidates(candidates, triage, client, use_cache=False)

    assert status == "ok"
    assert valid_indices == [0, 1]
    assert 999 not in valid_indices
    assert -5 not in valid_indices


def test_safe_mode_keeps_all_candidates_even_if_llm_ranks_few(mini_graph):
    """G1: SAFE mode never drops candidates even if LLM only ranks 1."""
    client = OllamaClient()
    mock_triage = Triage(change_kind="behavior", risk=2, summary="small change")
    mock_rank = Rank(order=[0])  # only ranks index 0

    def mock_chat_json(messages, schema, **kwargs):
        if schema == Triage:
            return mock_triage, "ok"
        return mock_rank, "ok"

    client.chat_json = MagicMock(side_effect=mock_chat_json)

    changed = [
        ChangedSymbol(
            file="pricing.py",
            qualname="pricing.apply_discount",
            kind="function",
            ast_equal=False,
        )
    ]
    selected, triage, guardrails, status = select_and_rank_tests(
        graph=mini_graph,
        changed_symbols=changed,
        diff_text="mock diff",
        client=client,
        mode="safe",
        use_cache=False,
    )
    assert status == "ok"
    assert "G1" in guardrails
    # Must keep all candidates found in graph (at least 4)
    assert len(selected) >= 4


def test_docs_only_ast_equal_skips_everything(mini_graph):
    """G2: Skip-all is allowed only if every changed symbol is AST-identical."""
    client = OllamaClient()
    changed = [
        ChangedSymbol(
            file="pricing.py",
            qualname="pricing.apply_discount",
            kind="function",
            ast_equal=True,
        )
    ]
    selected, triage, guardrails, status = select_and_rank_tests(
        graph=mini_graph,
        changed_symbols=changed,
        diff_text="# just comment change",
        client=client,
        mode="safe",
        use_cache=False,
    )
    assert "G2" in guardrails
    assert len(selected) == 0
    assert status == "skipped_deterministic"


def test_llm_says_docs_but_ast_changed_does_not_skip(mini_graph):
    """G2: Even if LLM says docs_or_format, if ast_equal is False, do NOT skip."""
    client = OllamaClient()
    # LLM hallucinates docs_or_format and risk=1
    mock_triage = Triage(change_kind="docs_or_format", risk=1, summary="claims docs only")
    mock_rank = Rank(order=[0])

    def mock_chat_json(messages, schema, **kwargs):
        if schema == Triage:
            return mock_triage, "ok"
        return mock_rank, "ok"

    client.chat_json = MagicMock(side_effect=mock_chat_json)

    changed = [
        ChangedSymbol(
            file="pricing.py",
            qualname="pricing.apply_discount",
            kind="function",
            ast_equal=False,  # AST actually changed!
        )
    ]
    selected, triage, guardrails, status = select_and_rank_tests(
        graph=mini_graph,
        changed_symbols=changed,
        diff_text="price * 2",
        client=client,
        mode="safe",
        use_cache=False,
    )
    # G2 should not fire, tests should NOT be skipped
    assert "G2" not in guardrails
    assert len(selected) > 0


def test_high_risk_widens_depth(mini_graph):
    """G5: risk >= 4 widens traversal depth and triggers G5."""
    client = OllamaClient()
    mock_triage = Triage(change_kind="behavior", risk=5, summary="critical core change")
    mock_rank = Rank(order=[0, 1])

    def mock_chat_json(messages, schema, **kwargs):
        if schema == Triage:
            return mock_triage, "ok"
        return mock_rank, "ok"

    client.chat_json = MagicMock(side_effect=mock_chat_json)

    changed = [
        ChangedSymbol(
            file="pricing.py",
            qualname="pricing.apply_discount",
            kind="function",
            ast_equal=False,
        )
    ]
    selected, triage, guardrails, status = select_and_rank_tests(
        graph=mini_graph,
        changed_symbols=changed,
        diff_text="diff ...",
        client=client,
        mode="safe",
        use_cache=False,
    )
    assert "G5" in guardrails
    assert triage.risk == 5


def test_budget_mode_returns_exactly_k_by_fused_rank(mini_graph):
    """Budget mode limits returned tests to exactly K."""
    client = OllamaClient()
    mock_triage = Triage(change_kind="behavior", risk=3, summary="standard change")
    mock_rank = Rank(order=[1, 0])

    def mock_chat_json(messages, schema, **kwargs):
        if schema == Triage:
            return mock_triage, "ok"
        return mock_rank, "ok"

    client.chat_json = MagicMock(side_effect=mock_chat_json)

    changed = [
        ChangedSymbol(
            file="pricing.py",
            qualname="pricing.apply_discount",
            kind="function",
            ast_equal=False,
        )
    ]
    selected, triage, guardrails, status = select_and_rank_tests(
        graph=mini_graph,
        changed_symbols=changed,
        diff_text="diff ...",
        client=client,
        mode="budget",
        budget_k=2,
        use_cache=False,
    )
    assert len(selected) == 2


def test_think_blocks_stripped():
    """Strip <think>...</think> blocks emitted by reasoning models."""
    raw = "<think>\nThinking about this code change...\nIt looks risky.\n</think>\n{\"status\": \"ok\"}"
    cleaned = strip_think_blocks(raw)
    assert "<think>" not in cleaned
    assert "Thinking about" not in cleaned
    assert cleaned == '{"status": "ok"}'
