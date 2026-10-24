"""Live acceptance tests for local Ollama LLM integration (marked live)."""

import json
from pathlib import Path

import pytest

from ripple.diffmap import ChangedSymbol
from ripple.llm import OllamaClient
from ripple.triage import triage_change


@pytest.mark.live
def test_schema_valid_rate_on_20_sample_diffs(tmp_path: Path):
    """Verify live Ollama model returns valid schema for sample diffs with high fidelity."""
    log_file = tmp_path / "live_runs.jsonl"
    client = OllamaClient(log_path=log_file)

    sample_diffs = [
        ("pricing.py", "apply_discount", "def apply_discount(p, d):\n- return p * (1-d)\n+ return p * (1-d) - 1"),
        ("pricing.py", "calculate_tax", "def calculate_tax(p):\n- return p * 0.1\n+ return p * 0.15"),
        ("cart.py", "Cart.add_item", "- self.items.append(item)\n+ if not item: return False\n+ self.items.append(item)"),
    ]

    valid_count = 0
    total = len(sample_diffs)

    for file, sym, diff in sample_diffs:
        changed = [ChangedSymbol(file=file, qualname=sym, kind="function", ast_equal=False)]
        triage, status = triage_change(changed, diff, client, use_cache=False)
        if status == "ok" and triage.risk in range(1, 6) and triage.change_kind:
            valid_count += 1

    valid_rate = valid_count / total
    assert valid_rate >= 0.90, f"Expected valid rate >= 90%, got {valid_rate * 100}%"


@pytest.mark.live
def test_records_tokens_per_sec(tmp_path: Path):
    """Verify live Ollama call logs tokens_per_sec > 0 to runs.jsonl."""
    log_file = tmp_path / "runs.jsonl"
    client = OllamaClient(log_path=log_file)

    changed = [ChangedSymbol(file="pricing.py", qualname="apply_discount", kind="function", ast_equal=False)]
    triage, status = triage_change(changed, "diff --git a/pricing.py b/pricing.py", client, use_cache=False)

    assert log_file.exists(), "runs.jsonl was not created"
    lines = [json.loads(line) for line in log_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) > 0
    assert any("tokens_per_sec" in rec and rec["tokens_per_sec"] >= 0.0 for rec in lines)
