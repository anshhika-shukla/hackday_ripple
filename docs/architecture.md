# RIPPLE: Architecture & Design

## 1. System Overview

RIPPLE is an offline change-impact and test-selection agent designed to accelerate developer feedback loops while maintaining safety and test recall.

```
git diff -> diffmap.py (changed functions) -> Graphify graph.json -> impact.py (reverse BFS, candidate tests)
   -> llm.py/triage.py (qwen3: kind, risk, rank) -> fusion + guardrails G1-G5 -> runner.py (pytest subset)
   -> report + ripple map
eval/: seeded mutants -> ground truth -> score strategies A/B/C
```

## 2. Target Repositories
- **Main target**: `mahmoud/boltons`, tag `26.2.0`: 519 tests, demo and headline evaluation.
- **Limitation case**: `pallets/click`, tag `8.1.7`: 611 tests, dynamic dispatch the static graph cannot follow.
- **Toy target**: `tests/fixtures/mini_app` (8 tests).
- All are cloned into `targets/` (git-ignored) by `scripts/setup_target.sh`, each with its own Graphify graph.

## 3. Data Flow & Core Modules
1. **diffmap.py**:
   - Parses unified git diffs (`git diff -U0`).
   - Uses Python's standard `ast` module to locate enclosing functions, methods, or classes for every modified line.
   - Detects AST equivalence (stripped docstrings and comments) to identify no-op changes (`ast_equal=True`).
2. **graphio.py**:
   - Normalizes Graphify's `graphify-out/graph.json` into typed `Node` and `Edge` structures.
   - Constructs a `networkx.DiGraph` representing calls, imports, and containment.
3. **impact.py**:
   - Performs reverse BFS traversal from changed symbols up to depth $D$ (default 3).
   - Identifies candidate test cases and direct/indirect caller distances.
   - Includes an import-closure fallback to capture tests importing modified modules even when dynamic dispatch prevents direct call edges.
4. **llm.py & triage.py**:
   - Communicates with local Ollama (`qwen3:4b-instruct` or fallback `qwen3:1.7b`).
   - Strips `<think>` tags and enforces strict Pydantic JSON schemas.
   - Classifies change kind (`behavior`, `signature`, `refactor`, `docs_or_format`).
   - Ranks candidate tests and fuses ranks using Reciprocal Rank Fusion (RRF) with graph distance.
5. **runner.py**:
   - Read-only test execution of the selected pytest subset with timeouts.
   - Parses JUnit XML for execution metrics, timing, and failure analysis.
6. **report.py & ripplemap.py**:
   - Generates structured JSON reports, markdown summaries, and a zero-dependency offline SVG ripple map.
7. **draft.py (Stretch Agentic Capability)**:
   - Discovers changed/impacted symbols lacking direct test coverage in the code graph.
   - Prompts the local LLM to synthesize targeted regression test cases.
   - **Guardrail**: Every candidate test is compiled and executed against the pre-change baseline; tests failing or erroring on baseline are rejected.

## 4. Guardrails

| ID | Name | Description |
|---|---|---|
| **G1** | Safe Mode Invariant | SAFE mode never drops a graph candidate because of the LLM. LLM only re-ranks. |
| **G2** | AST-Identity Skip | Skip-all is allowed only if every changed symbol is AST-identical (deterministic), never on LLM recommendation. |
| **G3** | Output Validation | LLM responses must strictly validate against Pydantic schemas; unknown test IDs/indices are discarded. |
| **G4** | Fail-Safe Fallback | Malformed output or timeout after 2 retries falls back cleanly to deterministic graph ranking. |
| **G5** | High-Risk Expansion | If `risk >= 4` or `change_kind == "signature"`, depth is expanded ($D+1$) and import-closure candidates are injected. |
| **G6** | Isolated Runner | Test execution is read-only on the target repository with strict per-test and total timeouts. |
