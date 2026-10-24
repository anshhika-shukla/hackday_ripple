# RIPPLE
Run the tests that matter. | **Track:** Narrow Agentic Tools | **Team:** <name + members>

## Problem Statement & Target User
Developers on slow suites / CI quotas either wait or skip tests and ship regressions.

## Approach, Architecture & Demo
Diff -> changed symbols -> Graphify graph ripple -> local LLM triage and ranking -> run selected pytest tests -> brief.
[demo video link] [docs/ripple_map.png]

## Model Details
- qwen3:<tag>, <params> B params, Apache-2.0 (verify), Ollama <version>, quantization <from ollama show>
- Hardware: <RAM / OS / CPU or GPU> | External APIs: none (fully offline, tested with Wi-Fi off)

## Setup Instructions
1. Python 3.10+, git, Ollama  2. pip install -r requirements.txt && pip install -e .
3. ollama pull qwen3:<tag>  4. bash scripts/setup_target.sh  5. bash scripts/demo.sh

## Results (3 runs)
<paste docs/results.md table, screenshots, tokens/sec, limitations>

## Graphify Integration
Graph: graphify-out/graph.html | Shared in Discord: yes | Licence: MIT
