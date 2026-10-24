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


def generate_brief(report: Report) -> str:
    """Generate a clean developer-facing Markdown brief."""
    status_icon = "✅" if report.results.get("failed", 0) == 0 else "❌"
    outcome_str = "PASSED" if report.results.get("failed", 0) == 0 else "FAILED"

    full_s = report.timing.get("full_suite_s", 15.0)
    test_s = report.timing.get("tests_s", 0.0)
    time_saved = max(0.0, round(full_s - test_s, 1))

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
        f"- **Ripple Scope**: Selected **{report.selected}** of **{report.suite_total or report.candidates_total}** tests ({report.candidates_total} candidates identified)",
        f"- **Execution Mode**: `{report.mode.upper()}` (LLM Status: `{report.llm_status}`)",
        f"- **Guardrails Triggered**: `{guardrails_text}`",
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
            f"- Pytest Subset Execution: {report.timing.get('tests_s', 0.0):.2f}s (Full suite: {full_s:.1f}s)",
            f"- **Estimated Time Saved**: **~{time_saved}s**",
        ]
    )

    return "\n".join(brief_lines)
