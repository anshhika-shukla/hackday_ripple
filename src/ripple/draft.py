"""Missing-test generator: drafts candidate pytests for untested changed symbols."""

import ast
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from ripple.diffmap import ChangedSymbol
from ripple.graphio import CodeGraph
from ripple.impact import CandidateTest, compute_impact
from ripple.llm import OllamaClient, strip_think_blocks


def find_uncovered_symbols(
    graph: CodeGraph,
    changed_symbols: list[ChangedSymbol],
) -> list[ChangedSymbol]:
    """Identify changed symbols that have no directly covering unit test in the graph."""
    candidates, _ = compute_impact(graph, changed_symbols, max_depth=1)
    covered_qualnames = set()
    for c in candidates:
        if c.direct and c.via:
            covered_qualnames.add(c.via[0])

    uncovered = []
    for s in changed_symbols:
        short_name = s.qualname.split(".")[-1]
        if s.qualname not in covered_qualnames and short_name not in covered_qualnames:
            uncovered.append(s)

    return uncovered


def draft_pytest_code(symbol: ChangedSymbol, client: OllamaClient) -> str:
    """Prompt local LLM to draft a minimal regression pytest for symbol."""
    system_prompt = (
        "You are an automated pytest generation agent.\n"
        "Given a Python function signature and source, write a single standalone unit test function.\n"
        "Requirements:\n"
        "- Name the function test_<symbol_name>_baseline\n"
        "- Only output executable Python code, no markdown fences, no explanations.\n"
        "- Assert expected baseline behavior."
    )

    src_snippet = symbol.old_src or symbol.new_src or f"def {symbol.qualname}(): pass"
    user_prompt = f"File: {symbol.file}\nSymbol: {symbol.qualname}\nSource:\n{src_snippet}\n/no_think"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        response = client._client.chat(
            model=client.model,
            messages=messages,
            options={"temperature": 0.0, "num_predict": 250},
        )
        content = response.get("message", {}).get("content", "")
    except Exception:
        # Fallback template test
        mod_name = Path(symbol.file).stem
        func_name = symbol.qualname.split(".")[-1]
        return f"from {mod_name} import {func_name}\n\ndef test_{func_name}_baseline():\n    assert callable({func_name})\n"

    cleaned = strip_think_blocks(content)
    # Strip markdown formatting if any was returned
    cleaned = re.sub(r"^```python\s*", "", cleaned)
    cleaned = re.sub(r"^```\s*", "", cleaned)
    cleaned = re.sub(r"```$", "", cleaned).strip()

    return cleaned


def verify_drafted_test_on_baseline(
    drafted_code: str,
    repo_path: Path,
) -> bool:
    """
    Guardrail: Test must compile and PASS on the pre-change baseline repository code.
    If it fails or raises an error, it is discarded.
    """
    try:
        # Verify syntax
        compile(drafted_code, "<drafted_test>", "exec")
    except Exception:
        return False

    with tempfile.NamedTemporaryFile("w", suffix=".py", dir=str(repo_path), delete=False) as tf:
        temp_file = Path(tf.name)
        temp_file.write_text(drafted_code, encoding="utf-8")

    try:
        cmd = ["pytest", "-q", "--tb=no", str(temp_file.name)]
        proc = subprocess.run(cmd, cwd=str(repo_path), capture_output=True, text=True, timeout=10.0)
        return proc.returncode == 0
    except Exception:
        return False
    finally:
        try:
            temp_file.unlink()
        except Exception:
            pass
