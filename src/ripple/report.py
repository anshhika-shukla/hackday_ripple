"""Report generation: JSON contract and Markdown brief."""

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class Report(BaseModel):
    mode: str = "safe"  # safe | budget
    model: str = "qwen3:4b-instruct"
    llm_status: str = "ok"  # ok | fallback | disabled | skipped_deterministic
    changed: list[dict[str, Any]] = Field(default_factory=list)
    candidates_total: int = 0
    selected: int = 0
    suite_total: int = 0
    results: dict[str, Any] = Field(default_factory=dict)
    timing: dict[str, float] = Field(default_factory=dict)
    tokens_per_sec: float = 0.0
    guardrails_fired: list[str] = Field(default_factory=list)
    triage: dict[str, Any] = Field(default_factory=dict)  # model's change_kind, risk, summary


def cases_run(results: dict[str, Any]) -> int:
    """Test cases pytest ran (a selected test function can expand into several parametrized cases)."""
    return results.get("passed", 0) + results.get("failed", 0) + results.get("skipped", 0)


def _scope_cases(report: Report) -> str:
    """Selected functions and the suite total are different units; state the suite in pytest test cases."""
    ran = cases_run(report.results)
    if ran and report.suite_total:
        return f"pytest ran **{ran}** of **{report.suite_total}** test cases ({100 * ran / report.suite_total:.1f}%)"
    return f"the suite has {report.suite_total} test cases" if report.suite_total else "suite size unknown"


def _triage_line(report: Report) -> str:
    """What the local model said about the change, or why it said nothing."""
    if report.llm_status == "ok" and report.triage:
        t = report.triage
        return f"- **Model's read** ({report.model}): {t.get('change_kind')} change, risk {t.get('risk')}/5. {t.get('summary', '')}"
    if report.llm_status == "fallback":
        return "- **Model's read**: model unavailable or invalid output; tests ranked by the graph only (G4)"
    if report.llm_status == "skipped_deterministic":
        return "- **Model's read**: not needed; the change is comments/docstrings only (G2)"
    return "- **Model's read**: model disabled (--no-llm); tests ranked by the graph only"


def generate_brief(report: Report) -> str:
    """Generate a clean developer-facing Markdown brief."""
    status_icon = "✅" if report.results.get("failed", 0) == 0 else "❌"
    outcome_str = "PASSED" if report.results.get("failed", 0) == 0 else "FAILED"

    full_s = report.timing.get("full_suite_s")
    test_s = report.timing.get("tests_s", 0.0)
    ripple_s = test_s + report.timing.get("graph_s", 0.0) + report.timing.get("llm_s", 0.0)

    symbols_list = []
    for s in report.changed:
        file = s.get("file", "")
        name = s.get("qualname", "")
        kind = s.get("kind", "")
        symbols_list.append(f"`{file}::{name}` ({kind})")
    symbols_text = ", ".join(symbols_list) if symbols_list else "None detected"

    guardrails_text = ", ".join(report.guardrails_fired) if report.guardrails_fired else "None"

    brief_lines = [
        f"## {status_icon} RIPPLE Test Selection Brief ({outcome_str})",
        "",
        f"- **Changed Symbols**: {symbols_text}",
        f"- **Ripple Scope**: Selected **{report.selected}** test functions ({report.candidates_total} candidates identified); {_scope_cases(report)}",
        f"- **Execution Mode**: `{report.mode.upper()}` (LLM Status: `{report.llm_status}`)",
        f"- **Guardrails Triggered**: `{guardrails_text}`",
        _triage_line(report),
        f"- **Results**: {report.results.get('passed', 0)} passed, {report.results.get('failed', 0)} failed",
    ]

    failed_ids = report.results.get("failed_ids", [])
    if failed_ids:
        brief_lines.append("")
        brief_lines.append("### 🚨 Caught Regressions:")
        for fid in failed_ids:
            brief_lines.append(f"- `{fid}`")

    brief_lines.extend(
        [
            "",
            "### ⏱️ Performance & Timing",
            f"- Graph Impact Analysis: {report.timing.get('graph_s', 0.0):.2f}s",
            f"- Local LLM Triage/Rank: {report.timing.get('llm_s', 0.0):.2f}s",
            f"- Pytest Subset Execution: {test_s:.2f}s",
        ]
    )
    if report.tokens_per_sec:
        brief_lines.append(f"- Model speed: {report.tokens_per_sec:.1f} tokens/sec")
    if full_s is not None:
        brief_lines.append(f"- Full suite (measured): {full_s:.2f}s vs RIPPLE total {ripple_s:.2f}s")

    return "\n".join(brief_lines)
