# RIPPLE

**Run the tests that matter. Offline change-impact and test-selection agent**

| **Track:** Narrow Agentic Tools | **Event:** Hacktoberfest 2026 - Hack Day Jaipur (LNMIIT) | **Licence:** MIT |
|---|---|---|

> *"Run ~10% of your tests. Catch the bug anyway. Fully offline."*

**In plain words:** before you push a change, RIPPLE tells you which tests it could break. It follows Graphify's map of which functions call which from your change to the tests, runs only those, and a small Qwen3 model on your own laptop explains the change and rates its risk. On the boltons library it ran 8.3% of the tests and still caught 44 of 46 planted bugs. When it cannot trace the code (Click wires itself up at run time), it plays safe and runs nearly everything.

**Team:** Eknoor, Anshika, Vaibhavi

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
- **External Network Access**: none at runtime (Ollama on localhost). Demo verified with Wi-Fi off.
- **Hardware tested**: Intel Core i7-13700HX, 15.7 GB RAM (7.6 GB visible to WSL2), NVIDIA RTX 4050 Laptop GPU 6 GB, Windows 11 + WSL2 Ubuntu 24.04
- **Measured**: 4.0B params, 59–73 tokens/sec warm on an NVIDIA RTX 4050 Laptop GPU (6 GB), Ollama 0.31.1
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

# 4. Install Graphify, then clone the evaluation targets (boltons, Click) and build their code graphs
uv tool install graphifyy
bash scripts/setup_target.sh
```
Steps 1-4 need internet once; everything after that runs offline.

### Running RIPPLE
```bash
# Dry run: triage changes and inspect selected tests
ripple check

# Run selected tests in SAFE mode
ripple check --run

# Run only the top 10 ranked tests in BUDGET mode
ripple check --mode budget --k 10 --run

# Generate standalone SVG ripple map
ripple map --out ripple_map.html

# Experimental, not evaluated: draft pytests for changed functions that have no test
ripple draft-tests --out tests/test_generated.py

# Install as git pre-push hook
ripple install-hook

# Launch local dashboard in browser (http://localhost:8000)
python scripts/serve.py
```

### Automated Demo
```bash
bash scripts/demo.sh            # plants a one-line bug in boltons, RIPPLE selects and runs tests, then restores
bash scripts/demo.sh mini_app   # same on the tiny shop app in tests/fixtures/mini_app
```

### Live demo on a project you edit yourself
```bash
bash scripts/setup_demo_project.sh                    # examples/canteen -> targets/canteen (8 modules, 44 tests)
# edit a line in targets/canteen (e.g. loyalty.py), then:
.venv/bin/python -m ripple.cli check --repo targets/canteen --run
bash scripts/check.sh targets/canteen                 # same, plus the dashboard's "Your latest check"
git -C targets/canteen checkout -- .                  # undo the edit
```

---

## 5. Benchmark Results & Ablation

We plant one-line bugs (seeded AST mutants on lines the tests execute), run the full suite to learn which tests really catch each one, then check whether RIPPLE's selection would have caught it.

**boltons 26.2.0** (519 tests; 60 planted bugs, 46 caught by the full suite):

| Strategy | Catch-Rate | Tests run | Failing test in top 3 | in top 10 |
|---|---:|---:|---:|---:|
| A: filename heuristic (`tests/test_<module>.py`) | 93.5% | 5.4% | 39.1% | 63.0% |
| B: Graphify graph only | 82.6% | 1.5% | 69.6% | 80.4% |
| **B + import fallback (SAFE, default)** | **95.7%** | **8.3%** | 69.6% | 80.4% |
| C: SAFE + local LLM ranking | 95.7% | 8.3% | 67.4% | 80.4% |

- **Claim we can back**: on boltons, RIPPLE ran 8.3% of the tests and still caught 44 of 46 bugs.
- **3 runs of C** (no LLM cache): identical (95.7% catch, 67.4% top-3); 70.8 tokens/sec on an RTX 4050 laptop GPU.
- **Where the AI helps and where it does not**: the model's change summary and risk rating appear in every brief; its test *ranking* adds no lift on boltons (67.4% vs 69.6% top-3) and a small one on Click (20% vs 16% top-10).
- **Demo bug** (`scripts/demo.sh`): `human_readable_list` returns "oranges and oranges"; RIPPLE selects 34 of 519 tests and catches `test_human_readable_list`, in ~1.5 s total. The full boltons suite took 1.8–6.2 s across our runs on this laptop.

**Limitation, measured on pallets/click 8.1.7** (611 tests; 40 bugs, 25 caught): Click calls into itself dynamically (`CliRunner.invoke(cli)` -> `cli.main()`), so the graph alone catches 12% and the SAFE fallback catches 96% only by running ~99% of tests. RIPPLE plays safe there instead of guessing.

Reproduce: `N=60 bash scripts/run_eval.sh boltons` (also `click`, `mini_app`). Full tables: [docs/results.md](docs/results.md)

---

## 6. Graphify Integration

- **Core Dependency**: RIPPLE directly uses Graphify's static code graph (`graphify extract . --code-only`) to discover call relations, class hierarchies, and import dependencies.
- **Graph Schema Documentation**: [docs/graph_schema.md](docs/graph_schema.md)
- **Repo Graph**: RIPPLE's own Graphify graph is in `graphify-out/` (`graph.html`, `graph.json`, `GRAPH_REPORT.md`), regenerated after the final commit with `bash scripts/graph.sh` (also makes `graph.html` work offline).
- **Shared in Discord**: yes, [link to our post](TODO-discord-message-link)
- **Target graphs**: `scripts/setup_target.sh` runs `graphify extract . --code-only` in each target; RIPPLE reads those `graph.json` files. `bash scripts/graph_libs.sh` builds a browsable, offline `graph.html` for each target (opened from the dashboard's library picker).

---

## 7. Licences

- **RIPPLE code**: MIT ([LICENSE](LICENSE))

**Third-party and model licences**

| Component | Role | Licence |
|---|---|---|
| Qwen3 4B (`qwen3:4b-instruct`) | local model | Apache-2.0 |
| Ollama | model runtime | MIT |
| Graphify (`graphifyy`) | code graph | Apache-2.0 |
| networkx | graph traversal | BSD-3-Clause |
| pydantic | schema validation | MIT |
| ollama (Python client) | model calls | MIT |
| pytest, pytest-xdist | test runner | MIT |
| coverage | evaluation harness | Apache-2.0 |
| rich | terminal output | MIT |
| vis-network 9.1.6 (bundled in `graphify-out/`) | code graph viewer | Apache-2.0 OR MIT |
| boltons | evaluation/demo target (not redistributed) | BSD-3-Clause |
| Click | evaluation target (not redistributed) | BSD-3-Clause |
