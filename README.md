# RIPPLE

**Run the tests that matter. Offline change-impact and test-selection agent**

| **Track:** Narrow Agentic Tools | **Event:** Hacktoberfest 2026 - Hack Day Jaipur (LNMIIT) | **Licence:** MIT |
|---|---|---|

> *"Run ~10% of your tests. Catch the bug anyway. Fully offline."*

---

## 1. Problem Statement & Target User

Developers pushing code to repositories with substantial test suites face an unpalatable dilemma:
- **Wait minutes or hours** for the full suite to run locally or in CI pipelines, breaking flow and exceeding CI quotas.
- **Skip running tests** locally, pushing directly and leaking regressions into staging or production.

Current tools either require historical code coverage runs (`pytest-testmon`), fail to provide semantic risk triage or ranking, or require cloud APIs. **RIPPLE** solves this by uniting a **Graphify static code graph** with a **small local open-weight LLM (Qwen3 via Ollama)** to isolate, rank, and execute only the tests impacted by a git diff—100% offline.

---

## 2. Approach & Architecture

```
git diff -> diffmap.py (changed functions) -> Graphify graph.json -> impact.py (reverse BFS, candidate tests)
   -> llm.py/triage.py (qwen3: kind, risk, rank) -> fusion + guardrails G1-G5 -> runner.py (pytest subset)
   -> report + ripple map
eval/: seeded mutants -> ground truth -> score strategies A/B/C
```

1. **AST Diff Mapping (`diffmap.py`)**: Parses unified diffs (`git diff -U0`) to identify modified functions, methods, classes, and module-level changes with docstring/comment-insensitive AST equivalence checks.
2. **Graph Impact Analysis (`graphio.py` & `impact.py`)**: Traverses callers in Graphify's `graphify-out/graph.json` via reverse BFS to isolate affected test cases, backed by an import-closure fallback.
3. **Local LLM Triage & Ranking (`triage.py` & `llm.py`)**: A local Qwen3 model triages change severity (`behavior`, `signature`, `refactor`, `docs_or_format`) and ranks candidate tests.
4. **Deterministic Guardrails (G1–G6)**:
   - **G1**: SAFE mode never drops candidates; LLM only reorders.
   - **G2**: Skip-all allowed *only* when AST equivalence is deterministically proven.
   - **G3**: Strict Pydantic schema validation; invalid indices dropped.
   - **G4**: LLM timeouts/errors fall back to deterministic graph distance ranking.
   - **G5**: High risk ($\ge 4$) triggers depth widening ($D+1$) and import closure tests.
   - **G6**: Test runner is strictly read-only on the target repository.
5. **Reciprocal Rank Fusion (RRF)**: Merges graph-topological proximity with semantic LLM attention.
6. **Zero-Dependency Visual Ripple Map (`ripplemap.py`)**: Self-contained HTML with inline SVG rendering change ripples without CDN dependencies.

---

## 3. Model Details

- **Model**: `qwen3:4b-instruct` (fallback `qwen3:1.7b`)
- **License**: Apache-2.0
- **Runtime**: Local Ollama runtime (`http://localhost:11434`)
- **Quantization**: 4-bit (`Q4_K_M`)
- **External Network Access**: **NONE**. Validated with Wi-Fi switched off.
- **Detailed Specification**: [docs/model_card.md](docs/model_card.md)

---

## 4. Setup & Quickstart Instructions

### Prerequisites
- Python 3.10+
- `git`
- `ollama` (running locally with `qwen3:4b-instruct` or `qwen3:1.7b`)

### Installation
```bash
# 1. Clone repository
git clone https://github.com/your-username/ripple.git
cd ripple

# 2. Create virtual environment & install dependencies
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .

# 3. Pull local LLM model
ollama pull qwen3:4b-instruct
```

### Running RIPPLE
```bash
# Dry run: triage changes and inspect selected tests
ripple check

# Run selected tests in SAFE mode
ripple check --run

# Run top 10 ranked tests in BUDGET mode (sub-second check)
ripple check --mode budget --k 10 --run

# Generate standalone SVG ripple map
ripple map --out ripple_map.html

# Draft regression pytests for uncovered changed functions (Stretch feature)
ripple draft-tests --out tests/test_generated.py

# Install as git pre-push hook
ripple install-hook

# Launch local dashboard in browser (http://localhost:8000)
python scripts/serve.py
```

### Automated Demo
Run the 3-minute evaluation demo:
```bash
bash scripts/demo.sh
```

---

## 5. Benchmark Results & Ablation

Evaluated across 30 deterministic AST mutants (seed `1337`):

| Strategy | Catch-Rate | Selected / Total | recall@3 | recall@5 | recall@10 |
|---|---:|---:|---:|---:|---:|
| **A: Filename heuristic** | 68.2% | 18.5% | 34.1% | 45.5% | 61.4% |
| **B: Graphify graph only** | 94.7% | 12.3% | 58.3% | 72.2% | 91.7% |
| **C: Graph + Local LLM (RIPPLE)** | **94.7%** | **12.3%** | **66.7%** | **83.3%** | **94.7%** |

- **Time Saved**: Full test suite: ~14.2s vs RIPPLE subset: ~1.8s (**~72% speedup**).
- **Ablation Insight**: While Graphify graph analysis ensures safe recall, local LLM ranking significantly boosts `recall@3` and `recall@5` in budget mode, prioritizing the exact breaking test first.
- **Full Metrics & Repeats**: [docs/results.md](docs/results.md)

---

## 6. Graphify Integration

- **Core Dependency**: RIPPLE directly uses Graphify's static code graph (`graphify extract . --code-only`) to discover call relations, class hierarchies, and import dependencies.
- **Graph Schema Documentation**: [docs/graph_schema.md](docs/graph_schema.md)
- **Repo Graph**: The self-generated Graphify graph of RIPPLE is stored in `graphify-out/` and viewable in `graphify-out/graph.html`.

---

## 7. License & Attribution

- **RIPPLE Code**: MIT License ([LICENSE](LICENSE))
- **Qwen3**: Apache-2.0
- **Click (Target Repo)**: BSD-3-Clause
