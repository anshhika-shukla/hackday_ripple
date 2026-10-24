# RIPPLE Model Card: Local Triage & Test Ranking

## 1. Model Overview
- **Model Architecture**: Qwen3 (`qwen3:4b-instruct` / `qwen3:1.7b`)
- **Developer / Provider**: Alibaba Qwen Team / Local execution via Ollama
- **License**: Apache-2.0
- **Runtime Environment**: Local Ollama runtime (`http://localhost:11434`)
- **Quantization**: 4-bit (`Q4_K_M` standard Ollama package)
- **External Network Access**: **NONE**. Fully offline, validated with Wi-Fi disabled.

## 2. Intended Use & Role in RIPPLE
- **Change Triage**: Classify git diff hunks into semantic categories (`behavior`, `signature`, `refactor`, `docs_or_format`).
- **Regression Risk Estimation**: Assess likelihood of ripple effects (score 1 to 5).
- **Candidate Test Ranking**: Order graph-discovered tests so high-risk tests run first in budget mode (`--mode budget --k 10`).
- **Explanation**: Generate a concise <= 240 char summary and up to 3 suspicious points for developer reporting.

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
- **Median Call Latency**: ~1.5s - 8s (hardware dependent)
- **Mean Tokens/Second**: ~12 - 45 tok/s (CPU / Metal / CUDA)
- **Schema Adherence**: > 95% on first attempt; 100% with retry / fallback.
