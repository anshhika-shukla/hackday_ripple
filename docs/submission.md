# RIPPLE: submission answers

Every number here comes from a real run; sources are linked in the README and [docs/results.md](results.md).

## 1. Submission form

| Field | Answer (copy-paste) |
|---|---|
| **Project name** | RIPPLE |
| **Tagline** | Run ~10% of your tests. Catch the bug anyway. No internet needed. |
| **Track** | Narrow Agentic Tools |
| **Team members** | Eknoor, Anshika, Vaibhavi |
| **Problem** | After changing one line, developers either wait for the whole test suite or skip it and push, which is how bugs reach users. Coverage-based test selection needs history from earlier runs, and AI tools usually send your code to a cloud API. |
| **Target user** | Python developers and student/open-source teams with pytest suites who want to know, before pushing, which tests a change could break, without sending code to the cloud. |
| **Core feature** | `ripple check --run` reads your git diff, follows Graphify's code graph from the changed functions to the tests that reach them, adds every test file that imports the changed file as a safety net, runs only those tests, and has a local Qwen3 model summarise the change and rate its risk. The model never removes tests. An offline impact chart shows why each test was picked. Measured on the boltons library: 44 of 46 planted bugs caught while running 8.3% of the tests. |
| **Demo link** | *(video link, once uploaded)* |
| **Repository** | https://github.com/anshhika-shukla/hackday_ripple |
| **Licence** | MIT |
| **Model information** | Qwen3 4B Instruct (`qwen3:4b-instruct`), 4.0B parameters, Apache-2.0, Ollama 0.31.1 on localhost, Q4_K_M 4-bit, NVIDIA RTX 4050 Laptop GPU (6 GB) + Intel Core i7-13700HX, 15.7 GB RAM; no external APIs at run time. |
| **Graphify integration** | RIPPLE reads Graphify's `graph.json` (`graphify extract . --code-only`) and walks its call/reference/inheritance edges backwards from the change to the tests. RIPPLE's own graph is in `graphify-out/` and shared in the Graphify Discord (link and image in the README, section 6). |

## 2. Model details

| Item | Value |
|---|---|
| Model | Qwen3 4B Instruct, Ollama tag `qwen3:4b-instruct` |
| Parameters | 4.0B (`ollama show qwen3:4b-instruct`) |
| Licence | Apache-2.0 |
| Runtime | Ollama 0.31.1, local server on `127.0.0.1:11434` |
| Quantization | Q4_K_M (4-bit) |
| Settings | temperature 0, context 4096 tokens, max 200 output tokens, thinking off |
| Hardware | NVIDIA RTX 4050 Laptop GPU 6 GB (model fully on GPU), Intel Core i7-13700HX, 15.7 GB RAM (7.6 GB given to WSL2), Windows 11 + WSL2 Ubuntu 24.04 |
| Speed | 43.5–73 tokens/sec warm across our runs; ~16 tokens/sec on a cold first call |
| External APIs | None at run time. `scripts/network_audit.py` recorded RIPPLE's only network connection during a real check: Ollama on `127.0.0.1:11434`. Internet is needed once for setup. Tested with Wi-Fi switched off on the demo laptop. |
| What the model does | Classifies the change, rates risk 1–5, writes a one-line summary, and re-orders the chosen tests. It cannot remove tests (guardrail G1); invalid output falls back to graph-only ranking (G4). |

## 3. Results to include
1. **Task success:** planted-bug evaluation. boltons: 44/46 bugs caught (95.7%) running 8.3% of tests; Click: 24/25 (96.0%) but running 99.4% (the limitation); mini_app: 18/18. Tables in the README and [results.md](results.md); per-bug view in `results.html`.
2. **Three repeated runs:**
   - 3 back-to-back demo runs, same 34 tests selected and the bug caught every time; 54.7 / 45.9 / 43.5 tokens/sec ([log](../eval/results/boltons/demo_3runs.log)).
   - 3 uncached runs of the model strategy over all planted bugs: identical results on every library; 70.8 / 67.8 / 71.1 tokens/sec mean.
3. **Screenshots:** `docs/screenshots/` (results page, impact chart, dashboard), shown in the README.
4. **Honest limits:** the model's re-ordering gives no lift on boltons and a small one on Click; no wall-clock saving on these fast suites; static graph misses run-time wiring (Click); Python + pytest only.

## 4. Likely judge questions
**How is this different from pytest-testmon?** Testmon needs a coverage database from earlier full runs. RIPPLE works on a fresh clone from a static code graph, and adds the model's change summary and risk rating.

**What if the graph misses a link (dynamic dispatch)?** Every test file that imports the changed file is also run. On Click, where the graph alone catches 12%, that fallback brings it to 96%, at the cost of running almost every test.

**Can the model skip a breaking test?** No. It only re-orders (G1). Tests are skipped only when an AST comparison proves only comments or docstrings changed (G2).

**Does it save time?** Not on these suites: the full boltons suite takes about 2 seconds, and RIPPLE's total (mostly the model) is about the same or longer. We haven't benchmarked a slow suite.

**Does it need the internet?** Not at run time: the only connection RIPPLE makes is to Ollama on localhost (measured). Setup needs internet once.
