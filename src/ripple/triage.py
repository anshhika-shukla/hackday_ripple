"""Triage, ranking, reciprocal rank fusion (RRF), and guardrails G1-G5."""

from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field

from ripple.diffmap import ChangedSymbol
from ripple.graphio import CodeGraph
from ripple.impact import CandidateTest, baseline_ranking_b, compute_impact
from ripple.llm import OllamaClient


class Triage(BaseModel):
    change_kind: Literal["behavior", "signature", "refactor", "docs_or_format", "unknown"] = "behavior"
    risk: int = Field(default=3, ge=1, le=5)
    summary: str = Field(default="", max_length=240)
    suspicious_points: list[str] = Field(default_factory=list)


class Rank(BaseModel):
    order: list[int] = Field(default_factory=list)


def triage_change(
    changed_symbols: list[ChangedSymbol],
    diff_text: str,
    client: OllamaClient,
    use_cache: bool = True,
) -> tuple[Triage, str]:
    """Classify change risk and kind via local LLM."""
    symbols_str = ", ".join(f"{s.file}::{s.qualname} ({s.kind})" for s in changed_symbols) or "None"
    diff_lines = diff_text.strip().splitlines()
    truncated_diff = "\n".join(diff_lines[:60])

    system_prompt = (
        "You are a code review assistant. You are given a unified diff hunk and the names of functions it changes.\n"
        "Classify the change and judge regression risk. Reply with JSON only, matching the schema. Be concise.\n"
        "change_kind: behavior = logic/return/condition changed; signature = params/return type/name changed;\n"
        "refactor = same behavior; docs_or_format = comments/docstrings/whitespace only.\n"
        "risk: 1 (trivial) to 5 (likely to break callers)."
    )

    user_prompt = f"Changed symbols: {symbols_str}\nDiff (truncated to 60 lines):\n{truncated_diff}\n/no_think"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    parsed, status = client.chat_json(messages, schema=Triage, use_cache=use_cache)
    if parsed is None or status != "ok":
        # Fallback triage
        return (
            Triage(
                change_kind="behavior",
                risk=3,
                summary="Fallback triage (graph-only mode)",
                suspicious_points=[],
            ),
            "fallback",
        )

    return parsed, "ok"


def rank_candidates(
    candidates: list[CandidateTest],
    triage: Triage,
    client: OllamaClient,
    use_cache: bool = True,
) -> tuple[list[int], str]:
    """Rank candidate tests via local LLM."""
    if not candidates:
        return [], "ok"

    # Chunk to max 25 candidates per call
    chunk = candidates[:25]
    lines = []
    for idx, c in enumerate(chunk):
        hint = (c.via[-1] if c.via else Path(c.file).stem)[:100]
        lines.append(f"{idx}. {c.test_id} | {hint} | dist={c.distance}")

    system_prompt = (
        "You rank unit tests by how likely they are to fail because of a code change. You get the change summary and a\n"
        "numbered list of candidate tests (name, one-line hint, graph distance). Reply JSON {\"order\":[indices]} listing\n"
        "the up to 15 most likely to fail first. Use only the given indices."
    )

    user_prompt = (
        f"Change: {triage.summary} (kind={triage.change_kind}, risk={triage.risk})\n"
        f"Candidates:\n" + "\n".join(lines) + "\n/no_think"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    parsed, status = client.chat_json(messages, schema=Rank, use_cache=use_cache)
    if parsed is None or status != "ok":
        return [], "fallback"

    # Guardrail G3: unknown indices are discarded
    valid_indices = [idx for idx in parsed.order if 0 <= idx < len(chunk)]
    return valid_indices, "ok"


def reciprocal_rank_fusion(
    graph_ranked: list[CandidateTest],
    llm_order: list[int],
    k: int = 60,
    w_graph: float = 1.0,
    w_llm: float = 1.5,
) -> list[CandidateTest]:
    """
    RRF combination of graph ranking B and LLM ranking.
    Formula: Score = w_graph / (k + rank_graph) + w_llm / (k + rank_llm)
    """
    # Map candidate to graph rank (1-indexed)
    graph_rank_map = {c.test_id: i + 1 for i, c in enumerate(graph_ranked)}

    # Map candidate to LLM rank
    llm_rank_map: dict[str, int] = {}
    for llm_pos, cand_idx in enumerate(llm_order):
        if cand_idx < len(graph_ranked):
            cand = graph_ranked[cand_idx]
            llm_rank_map[cand.test_id] = llm_pos + 1

    fused_candidates = []
    for cand in graph_ranked:
        r_g = graph_rank_map.get(cand.test_id, 1000)
        r_l = llm_rank_map.get(cand.test_id, 1000)

        score_rrf = (w_graph / (k + r_g)) + (w_llm / (k + r_l))
        # Keep original candidate attributes, update score
        fused = cand.model_copy()
        fused.score = score_rrf
        fused_candidates.append(fused)

    fused_candidates.sort(key=lambda c: (-c.score, c.distance, c.test_id))
    return fused_candidates


def select_and_rank_tests(
    graph: CodeGraph,
    changed_symbols: list[ChangedSymbol],
    diff_text: str,
    client: OllamaClient,
    mode: str = "safe",  # safe | budget
    budget_k: int = 10,
    no_llm: bool = False,
    use_cache: bool = True,
) -> tuple[list[CandidateTest], Triage, list[str], str]:
    """
    Main pipeline integrating change impact, LLM triage, RRF, and guardrails G1-G5.
    Returns (selected_tests, triage, guardrails_fired, llm_status).
    """
    guardrails_fired: list[str] = []

    # G2: Skip-all is allowed ONLY if every changed symbol is AST-identical (deterministic)
    if changed_symbols and all(s.ast_equal for s in changed_symbols):
        guardrails_fired.append("G2")
        triage = Triage(
            change_kind="docs_or_format",
            risk=1,
            summary="Deterministic AST check: all changed symbols are AST-identical. Safe to skip tests.",
            suspicious_points=[],
        )
        return [], triage, guardrails_fired, "skipped_deterministic"

    # Step 1: Initial Graph Impact computation
    candidates, _ = compute_impact(graph, changed_symbols, max_depth=3, include_import_closure=True)
    graph_ranked = baseline_ranking_b(candidates)

    if no_llm:
        triage = Triage(
            change_kind="behavior",
            risk=3,
            summary="LLM disabled via --no-llm flag",
            suspicious_points=[],
        )
        if mode == "budget":
            return graph_ranked[:budget_k], triage, guardrails_fired, "disabled"
        return graph_ranked, triage, guardrails_fired, "disabled"

    # Step 2: LLM Triage
    triage, triage_status = triage_change(changed_symbols, diff_text, client, use_cache=use_cache)
    llm_status = triage_status

    # G5: risk >= 4 or change_kind == signature -> widen: depth + 1 and add import-closure tests
    if triage.risk >= 4 or triage.change_kind == "signature":
        guardrails_fired.append("G5")
        candidates, _ = compute_impact(graph, changed_symbols, max_depth=4, include_import_closure=True)
        graph_ranked = baseline_ranking_b(candidates)

    if not graph_ranked:
        return [], triage, guardrails_fired, llm_status

    # Step 3: LLM Rank
    llm_indices, rank_status = rank_candidates(graph_ranked, triage, client, use_cache=use_cache)
    if rank_status != "ok" or triage_status != "ok":
        guardrails_fired.append("G4")
        llm_status = "fallback"
        # G4: fallback to graph-only ranking
        if mode == "budget":
            return graph_ranked[:budget_k], triage, guardrails_fired, "fallback"
        return graph_ranked, triage, guardrails_fired, "fallback"

    # G3 fired if any indices were discarded
    # Step 4: Reciprocal Rank Fusion
    fused = reciprocal_rank_fusion(graph_ranked, llm_indices)

    # Step 5: Selection based on mode
    if mode == "budget":
        selected = fused[:budget_k]
    else:
        # G1: SAFE mode never drops a graph candidate because of the LLM
        guardrails_fired.append("G1")
        selected = fused

    return selected, triage, guardrails_fired, "ok"
