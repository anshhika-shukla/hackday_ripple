# RIPPLE: Hack Day Jaipur Submission Answers & Pitch Notes

## 1. Official Submission Form Fields

| Submission Field | Final Text (Ready to Copy-Paste) |
|---|---|
| **Project Name** | RIPPLE |
| **Track** | Narrow Agentic Tools (Fully Local & Offline) |
| **Tagline** | Run ~10% of your tests. Catch the bug anyway. Fully offline. |
| **Problem Statement** | Developers pushing changes to test suites either wait on long full-suite runs or skip running tests locally, leaking regressions into production. Small teams and students with limited CI minutes or working offline lack intelligent, privacy-preserving test selection. |
| **Target User** | Software engineers, open-source contributors, and development teams running slow test suites with limited CI budgets or strict offline/air-gapped privacy requirements. |
| **Core Feature** | Static code graph impact analysis (Graphify) paired with an open-weight local LLM (Qwen3 via Ollama) that triages changes, ranks affected tests, executes the critical pytest subset, and provides a root-cause explanation. |
| **Models Used** | `qwen3:4b-instruct` / `qwen3:1.7b` running on local Ollama (`localhost:11434`). Quantization: `Q4_K_M`. License: Apache-2.0. External APIs: None (tested with Wi-Fi disabled). |
| **Graphify Integration** | RIPPLE consumes Graphify's static code graph (`graphify extract . --code-only`) to perform reverse BFS caller traversal and import-closure analysis. RIPPLE's own code graph is committed in `graphify-out/` and shared in the Discord event channel. |
| **Repository URL** | https://github.com/<your-username>/ripple |
| **License** | MIT License |

---

## 2. 3-Minute Demo Pitch Script (Timed)

| Time Window | Visual / Screen Action | Spoken Script |
|---|---|---|
| **0:00 – 0:30** | Show full test suite terminal run (`pytest`) taking ~15–30 seconds. | *"Every developer knows the pain of pushing a one-line change and waiting on the full test suite, or skipping tests and breaking production. CI quotas run out, and cloud test-selection tools require paid hosted APIs and warm coverage databases. RIPPLE solves this locally and offline."* |
| **0:30 – 1:30** | Execute `bash scripts/demo.sh`. A one-line bug is planted in boltons' `human_readable_list`; RIPPLE selects 34 of 519 tests, catches `test_human_readable_list`, and restores the code. The impact chart opens in the browser. | *"Here we plant a typo-sized bug: a function that should print 'apples and oranges' now prints 'oranges and oranges'. RIPPLE reads the diff, follows Graphify's code graph from that function to the tests that reach it, and runs only those: 34 of 519. A Qwen3 model on this laptop explains the change and rates its risk. The failing test is caught."* |
| **1:30 – 2:15** | Dashboard (`python scripts/serve.py`) → boltons → impact chart, and the brief in the terminal. Highlight Guardrails G1–G6. | *"This chart shows why RIPPLE picked those tests: your change in orange in the middle, the code that uses it, and the tests that check it in blue, with the one that caught the bug outlined. Crucially, RIPPLE is guarded: Guardrail G1 guarantees the LLM can never drop tests in SAFE mode, G2 ensures skip-all requires AST equivalence proof, and G6 keeps test execution isolated and read-only."* |
| **2:15 – 2:45** | Results page (`results.html`), boltons tab, then the Click tab. | *"We don't just demo RIPPLE; we measured it with 60 seeded one-line bugs on the boltons library: RIPPLE runs 8.3% of the tests and still catches 44 of the 46 bugs the full suite catches, identical across 3 runs. On Click, which wires itself up at run time, it falls back to running nearly everything."* |
| **2:45 – 3:00** | Turn off Wi-Fi or show airplane mode. Show `ripple check`. | *"RIPPLE runs 100% offline with zero CDN dependencies or external APIs. It's ready to install as a pre-push hook today."* |

---

## 3. Defense Against Likely Judge Questions

### Q1: How does RIPPLE differ from `pytest-testmon`?
> *"Testmon relies on dynamic coverage databases generated from previous full test runs. RIPPLE uses a **static code graph**, meaning it works immediately on a fresh clone with zero execution history. Furthermore, RIPPLE adds semantic change triage, budget-mode ranking, and human-readable risk briefs."*

### Q2: What happens if static analysis misses an edge (e.g. dynamic dispatch)?
> *"We implemented an **import-closure fallback**: any test file that transitively imports a modified module is included as a safety candidate. Furthermore, we don't guess our accuracy—we measured our recall empirically against seeded mutants (95.7% catch rate at 8.3% of tests on boltons; on Click the fallback is what keeps it safe)."*

### Q3: Can the LLM hallucinate and skip breaking tests?
> *"No. Guardrail **G1** enforces that in SAFE mode, all graph-discovered candidate tests are executed; the LLM is only permitted to reorder them and generate explanations. Guardrail **G2** only permits test-skipping if a deterministic AST comparison proves the change was comment- or docstring-only."*

### Q4: Does RIPPLE need internet access at any stage?
> *"Zero internet required. The inference runs on localhost via Ollama, Graphify's code-only mode uses local tree-sitter parsers, and our SVG ripple maps have no CDN dependencies."*
