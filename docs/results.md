# RIPPLE Evaluation & Mutation Results

All numbers below are produced by `bash scripts/run_eval.sh <target>`; raw data lives in
`eval/data/ground_truth_<target>.json` and `eval/results/<target>/strategy_*.json`.

## 1. Setup
- **Ground truth**: deterministic AST mutants (seed `1337`; operators CMP_FLIP, ARITH, CONST_OFF_BY_ONE, BOOL_NEGATE, RETURN_NONE) applied one at a time to library code (boltons: only lines the suite executes, measured with `coverage`); the full suite is run for each to record which tests really fail. Each mutant changes a single expression, like a one-line bug.
- **Selection** is computed offline from the mutant's location (mapped to its enclosing function, as `diffmap` does for a real diff) and the original Graphify graph. Mutants keep call structure, so the graph is still valid.
- **Strategies**
  - **A: filename heuristic** (no graph): every test in `tests/test_<module>.py`.
  - **B graph only**: reverse traversal of Graphify call/reference/inheritance edges, depth 3.
  - **B + import closure** (SAFE default): B plus every test file that transitively imports the changed file.
  - **C: B + import closure, ranked by local LLM** (Qwen3 triage + rank, reciprocal rank fusion).
- **Metrics**: catch-rate = mutants whose failing tests intersect the selection / mutants the full suite kills. Selection ratio = selected test functions / all test functions. recall@K = catch-rate when only the top K ranked tests run.

## 2. boltons 26.2.0 (519 tests, 413 test functions) — main result
60 mutants on covered lines of `boltons/`, 46 killed by the full suite (run with pytest-xdist, checked to give the same results as a serial run).

| Strategy | Catch-rate | Selected / Total | recall@3 | recall@5 | recall@10 |
|---|---:|---:|---:|---:|---:|
| A: filename heuristic | 93.5% | 5.4% | 39.1% | 50.0% | 63.0% |
| B: Graphify graph only | 82.6% | 1.5% | 69.6% | 78.3% | 80.4% |
| B + import closure (SAFE) | 95.7% | 8.3% | 69.6% | 78.3% | 80.4% |
| C: B + closure + local LLM rank | 95.7% | 8.3% | 67.4% | 78.3% | 80.4% |

Strategy C, 3 runs with the LLM response cache disabled: identical (catch 95.7%, recall@3 67.4%, recall@10 80.4%). Mean speed 70.8 tokens/sec.

**Reading it**
- SAFE mode catches 44 of 46 bugs while running 8.3% of tests.
- boltons keeps one test file per module, so the filename heuristic is strong (93.5% catch at 5.4%); the graph puts a failing test in the top 3 far more often (69.6% vs 39.1%) and follows cross-module calls.
- LLM ranking gives no lift here (recall@3 67.4% vs 69.6%). The model's visible contribution is the change summary and risk rating in the brief.

## 3. pallets/click 8.1.7 (611 tests, 315 test functions, full suite 0.85 s)
40 mutants in `src/click`, 25 killed by the full suite.

| Strategy | Catch-rate | Selected / Total | recall@3 | recall@5 | recall@10 |
|---|---:|---:|---:|---:|---:|
| A: filename heuristic | 24.0% | 3.2% | 8.0% | 12.0% | 16.0% |
| B: Graphify graph only | 12.0% | 3.9% | 8.0% | 8.0% | 8.0% |
| B + import closure (SAFE) | 96.0% | 99.4% | 12.0% | 12.0% | 16.0% |
| C: B + closure + local LLM rank | 96.0% | 99.4% | 16.0% | 16.0% | 20.0% |

Strategy C, 3 runs with the LLM response cache disabled: catch-rate 96.0 / 96.0 / 96.0, recall@10 20.0 / 20.0 / 20.0 (no variance at temperature 0). Mean speed 67.8 tokens/sec.

**What this shows, honestly**
- On Click the static call graph alone misses most bugs (12%). Click is driven through dynamic dispatch (`CliRunner.invoke(cli)` calls `cli.main()`), decorators and `click.X` attribute access, which Graphify's code-only graph does not resolve to the library functions.
- The import-closure fallback restores safety (96%) but selects almost the whole suite, because every test imports `click`, which re-exports every module.
- The LLM ranking gives a small lift over graph ranking at small K (recall@3 16% vs 12%, recall@10 20% vs 16%).

## 4. tests/fixtures/mini_app (8 tests, full suite 0.24 s)
26 mutants (all mutable points), 18 killed.

| Strategy | Catch-rate | Selected / Total | recall@3 | recall@5 | recall@10 |
|---|---:|---:|---:|---:|---:|
| A: filename heuristic | 94.4% | 27.8% | 94.4% | 94.4% | 94.4% |
| B: Graphify graph only | 100.0% | 44.4% | 100.0% | 100.0% | 100.0% |
| B + import closure (SAFE) | 100.0% | 56.9% | 100.0% | 100.0% | 100.0% |
| C: B + closure + local LLM rank | 100.0% | 56.9% | 100.0% | 100.0% | 100.0% |

Strategy C, 3 runs without cache: identical (100.0% each). Mean speed 71.1 tokens/sec. The app is too small for recall@K to separate strategies.

## 5. Timing (demo bug in boltons, `bash scripts/demo.sh`)
- Bug: `strutils.human_readable_list` returns `items[1]` twice. RIPPLE selects 34 of 519 tests and catches `tests/test_strutils.py::test_human_readable_list`.
- Graph impact 0.05 s, local LLM triage + rank ~1.1 s uncached, selected tests 0.36 s: ~1.5 s total.
- Full boltons suite: 1.8–6.2 s across our runs on this laptop (it varies run to run), so the saving is a few seconds here. Larger suites would save more in absolute terms; we have not measured one.

## 6. Model & hardware
`qwen3:4b-instruct` (4.0B params, Q4_K_M, Apache-2.0) on Ollama 0.31.1, NVIDIA RTX 4050 Laptop GPU (6 GB), WSL2 Ubuntu 24.04. 59–73 tokens/sec warm, ~16 tokens/sec on the first (cold) call. Wi-Fi-off run: not yet verified.

## 7. Known limitations
1. Static graph misses dynamic dispatch and decorator-based APIs (see Click results).
2. Import closure through package `__init__` re-exports degenerates to "run everything".
3. Python + pytest only; mutants keep call structure.
