# RIPPLE Model Card: Local Triage & Test Ranking

## 1. Model Overview
- **Model Architecture**: Qwen3 (`qwen3:4b-instruct`; other Ollama models can be set with `RIPPLE_MODEL` but were not evaluated)
- **Developer / Provider**: Alibaba Qwen Team / Local execution via Ollama
- **License**: Apache-2.0
- **Runtime Environment**: Local Ollama runtime (`http://localhost:11434`)
- **Quantization**: 4-bit (`Q4_K_M` standard Ollama package)
- **Parameters**: 4.0B (`ollama show qwen3:4b-instruct`)
- **External Network Access**: none at runtime. `scripts/network_audit.py` recorded RIPPLE's only connection during a real check: Ollama on `127.0.0.1:11434`. A Wi-Fi-off run has not been recorded.

## 2. Intended Use & Role in RIPPLE
- **Change Triage**: Classify git diff hunks into semantic categories (`behavior`, `signature`, `refactor`, `docs_or_format`).
- **Regression Risk Estimation**: Assess likelihood of ripple effects (score 1 to 5).
- **Candidate Test Ranking**: Order graph-discovered tests so high-risk tests run first in budget mode (`--mode budget --k 10`).
- **Explanation**: Generate a concise <= 240 char summary of the change, shown in the terminal brief, impact chart and dashboard.

## 3. Operational Parameters
| Parameter | Value | Rationale |
|---|---|---|
| `temperature` | `0.0` | Maximum determinism and schema adherence |
| `num_ctx` | `4096` | Accommodate diff context and candidate test lists |
| `num_predict` | `200` | Keep response latency under tens of seconds on CPU/laptop |
| `keep_alive` | `30m` | Avoid repeated model reloading between git commits |
| `think` | `false` | Explicitly turn off extended thinking tokens |

## 4. Guardrails & Safety Boundary
The LLM operates within strict deterministic guardrails:
1. **G1 (Safe Mode Invariant)**: In SAFE mode, the LLM **cannot** drop tests. It only reorders tests and generates explanations.
2. **G2 (Deterministic Skip)**: Skip-all is only permitted if AST comparison proves semantic identity (`ast_equal == True`). The LLM cannot veto test execution on changed code.
3. **G3 (Schema Validation)**: Responses are parsed via Pydantic (`Triage`, `Rank`). Invalid test indices are dropped.
4. **G4 (Deterministic Fallback)**: If the LLM produces invalid JSON or times out after 2 retries, RIPPLE automatically falls back to graph-distance ranking.
5. **G5 (Risk-Based Expansion)**: High risk ($\ge 4$) triggers graph neighborhood expansion ($D+1$) and import closure.

## 5. Performance Metrics
Measured on an NVIDIA RTX 4050 Laptop GPU (6 GB), WSL2 Ubuntu 24.04, Ollama 0.31.1, `qwen3:4b-instruct` fully on GPU:
- **Tokens/second**: 70.8 (boltons eval, 3 runs), 67.8 (Click eval, 3 runs); 54.7 / 45.9 / 43.5 in 3 back-to-back demo runs; ~16 on the first cold call (the demo preloads the model)
- **Triage + rank latency**: about 1–3.5 s per change (uncached) across our runs
- **Schema adherence**: live tests (`pytest -m live`, 3 sample diffs) pass; fallback rate over the eval is not recorded yet
