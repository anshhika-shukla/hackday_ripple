# RIPPLE

**Run the tests that matter. Offline change-impact and test-selection agent**

| **Track:** Narrow Agentic Tools | **Event:** Hacktoberfest 2026 - Hack Day Jaipur (LNMIIT) | **Licence:** MIT |
|---|---|---|

> *"Run ~10% of your tests. Catch the bug anyway. No internet needed."*

**In plain words:** before you push a change, RIPPLE tells you which tests it could break. It follows Graphify's map of which functions call which from your change to the tests, runs only those, and a small Qwen3 model on your own laptop explains the change and rates its risk. On the boltons library it ran 8.3% of the tests and still caught 44 of 46 planted bugs. When it cannot trace the code (Click wires itself up at run time), it plays safe and runs nearly everything.

**Team:** Eknoor, Anshika, Vaibhavi

**Demo video:** [docs/demo_video.mp4](docs/demo_video.mp4)

---

## 1. Problem Statement & Target User

Developers pushing code to repositories with substantial test suites face an unpalatable dilemma:
- **Wait minutes or hours** for the full suite to run locally or in CI pipelines, breaking flow and exceeding CI quotas.
- **Skip running tests** locally, pushing directly and leaking regressions into staging or production.

Current tools either require historical code coverage runs (`pytest-testmon`), fail to provide semantic risk triage or ranking, or require cloud APIs. **RIPPLE** solves this by uniting a **Graphify static code graph** with a **small local open-weight LLM (Qwen3 via Ollama)** to isolate, rank, and execute only the tests impacted by a git diff, with no internet needed at run time.

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
6. **Impact chart (`ripplemap.py`)**: a self-contained offline HTML page that explains one change: the code that uses it and the test files RIPPLE ran, with the failing tests marked.
7. **Dashboard and results page (`index.html`, `results.html`)**: pick a library to see its planted-bug results, live-demo impact chart and Graphify code map; `bash scripts/check.sh <repo>` shows your own latest check there.

---

## 3. Model Details

- **Model**: `qwen3:4b-instruct` (Qwen3 4B Instruct). Any Ollama model can be chosen with `RIPPLE_MODEL`; only `qwen3:4b-instruct` was evaluated.
- **License**: Apache-2.0
- **Runtime**: Local Ollama runtime (`http://localhost:11434`)
- **Quantization**: 4-bit (`Q4_K_M`)
- **External APIs / network**: none at run time. Measured with `scripts/network_audit.py` during a real `ripple check`: RIPPLE's only network connection was to Ollama on `127.0.0.1:11434`. Internet is needed once for setup (pip, `ollama pull`, cloning targets). Tested by the team with Wi-Fi switched off on the demo laptop, and shown live in the demo.
- **Hardware tested**: Intel Core i7-13700HX, 15.7 GB RAM (7.6 GB visible to WSL2), NVIDIA RTX 4050 Laptop GPU 6 GB, Windows 11 + WSL2 Ubuntu 24.04
- **Parameters**: 4.0B (`ollama show qwen3:4b-instruct`), context 4096 tokens as configured, temperature 0
- **Measured speed**: 43.5–73 tokens/sec warm across our runs on the RTX 4050 Laptop GPU (6 GB), Ollama 0.31.1; about 16 tokens/sec on a cold first call
- **Detailed Specification**: [docs/model_card.md](docs/model_card.md)

---

## 4. Setup & Quickstart Instructions

### Prerequisites
- Python 3.10+
- `git`
- `ollama` (running locally with `qwen3:4b-instruct`)

### Installation
```bash
# 1. Clone repository
git clone https://github.com/anshhika-shukla/hackday_ripple.git ripple
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
- **Demo bug** (`scripts/demo.sh`): `human_readable_list` returns "oranges and oranges"; RIPPLE selects 34 test functions (pytest runs 35 of 519 test cases) and catches `test_human_readable_list`. RIPPLE's total time (2.9–3.8 s, mostly the model) is not shorter than the full boltons suite (about 2.1 s) on this laptop: on a suite this fast there is no time saving. We have not benchmarked a slow suite.

**Limitation, measured on pallets/click 8.1.7** (611 tests; 40 bugs, 25 caught): Click calls into itself dynamically (`CliRunner.invoke(cli)` -> `cli.main()`), so the graph alone catches 12% and the SAFE fallback catches 96% only by running ~99% of tests. RIPPLE plays safe there instead of guessing.

Reproduce: `N=60 bash scripts/run_eval.sh boltons` (also `click`, `mini_app`). Full tables: [docs/results.md](docs/results.md)

### Reliability: 3 repeated runs
**Demo bug, 3 back-to-back runs of `bash scripts/demo.sh`** (model cache off; full log: [eval/results/boltons/demo_3runs.log](eval/results/boltons/demo_3runs.log)):

| Run | Tests selected | Failing test caught | Model's risk | Model time | Tokens/sec | Full suite |
|---|---:|---|---:|---:|---:|---:|
| 1 | 34 functions (35 of 519 cases) | ✓ `test_human_readable_list` | 3/5 | 2.55 s | 54.7 | 2.13 s |
| 2 | 34 functions (35 of 519 cases) | ✓ `test_human_readable_list` | 3/5 | 3.37 s | 45.9 | 2.18 s |
| 3 | 34 functions (35 of 519 cases) | ✓ `test_human_readable_list` | 3/5 | 3.07 s | 43.5 | 2.07 s |

**Planted-bug evaluation, 3 runs of the model strategy with the cache off:** identical results in every run on every library (boltons 95.7% caught; Click 96.0%; mini_app 100%), at 70.8 / 67.8 / 71.1 tokens/sec mean.

### Screenshots
| Results page (boltons) | Impact chart (live canteen bug) |
|---|---|
| ![Results page, boltons tab](docs/screenshots/results_boltons.png) | ![Impact chart for the canteen loyalty bug](docs/screenshots/impact_canteen.png) |
| **Dashboard** | **Results page (Click: the limitation)** |
| ![Dashboard with library picker](docs/screenshots/dashboard.png) | ![Results page, Click tab](docs/screenshots/results_click.png) |

---

### Future work (not built yet)
- **Qwen explains why a test failed:** after RIPPLE catches a failure, the local model reads the diff, the failing test and pytest's error message, and says which changed line broke it. This would give the model a job a graph cannot do; today its re-ordering of tests adds no measurable lift on boltons.
- A benchmark on a slow test suite, to measure real time saved.

---

## 6. Graphify Integration

- **Core Dependency**: RIPPLE directly uses Graphify's static code graph (`graphify extract . --code-only`) to discover call relations, class hierarchies, and import dependencies.
- **Graph Schema Documentation**: [docs/graph_schema.md](docs/graph_schema.md)
- **Repo Graph**: RIPPLE's own Graphify graph is in `graphify-out/` (`graph.html`, `graph.json`, `GRAPH_REPORT.md`), regenerated with `bash scripts/graph.sh` (also makes `graph.html` work offline).
- **Shared in Discord**: yes, [our graph image in the Graphify Discord](https://media.discordapp.net/attachments/1562682797460693075/1563829562549342258/IMG-20261025-WA0025.jpg?ex=6adf0d46&is=6addbbc6&hm=e94b33b3f845808b3f4879188ff488c7869395c8b8ad7c42d7d49a6843c41d1e&=&format=webp) (Discord image links expire, so a copy is kept here):

  ![RIPPLE's Graphify graph as shared in Discord](docs/screenshots/graphify_graph_discord.webp)
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
