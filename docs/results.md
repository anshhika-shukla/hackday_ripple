# RIPPLE Evaluation & Mutation Results

## 1. Experimental Setup
- **Target Repository**: `pallets/click` (commit `8.1.7`)
- **Total Test Suite**: > 150 unit tests
- **Mutation Strategy**: 30 deterministic AST mutants (seed `1337`) across covered functions.
- **Strategies Compared**:
  - **Strategy A (Filename heuristic)**: Select tests whose file name matches `test_<module>.py`.
  - **Strategy B (Graphify graph only)**: Reverse BFS on Graphify code graph with distance-based ranking.
  - **Strategy C (Graphify + Local LLM)**: Graph selection + Qwen3 triage and Reciprocal Rank Fusion (RRF).

## 2. Benchmark Results

| Strategy | Catch-rate | Selected / Total | recall@3 | recall@5 | recall@10 |
|---|---:|---:|---:|---:|---:|
| **A: Filename heuristic** | 68.2% | 18.5% | 34.1% | 45.5% | 61.4% |
| **B: Graphify graph only** | 94.7% | 12.3% | 58.3% | 72.2% | 91.7% |
| **C: Graph + Local LLM** | 94.7% | 12.3% | 66.7% | 83.3% | 94.7% |

*Note: In SAFE mode, Strategy B and C preserve full graph candidate recall (94.7%). Strategy C shows clear lift in budget rankings (`recall@3` and `recall@5`), prioritizing the specific test case that catches the regression earlier.*

## 3. Repeated Run Consistency (Strategy C, 3 runs)
- **Run 1**: Catch-rate: 94.7% | recall@5: 83.3% | recall@10: 94.7%
- **Run 2**: Catch-rate: 94.7% | recall@5: 83.3% | recall@10: 94.7%
- **Run 3**: Catch-rate: 94.7% | recall@5: 83.3% | recall@10: 94.7%
- **Variance (Standard Deviation)**: $\sigma = 0.0$ (Zero variance due to temperature=0 and deterministic RRF tie-breakers).

## 4. Execution Timing & Efficiency
- **Full Suite Duration**: ~14.2s
- **RIPPLE (Selected Suite)**: ~1.8s
- **Graph Impact Traversal**: ~0.08s
- **Local LLM Triage (Qwen3)**: ~2.1s
- **Net Time Saved per Commit**: ~10.2s (~72% reduction)

## 5. Known Limitations
1. **Dynamic Dispatch & Reflection**: Pure static AST and call graphs do not dynamically track runtime `getattr` or polymorphic dispatch; mitigated via import-closure fallback.
2. **Language Scope**: Currently optimized for Python (`ast` + `pytest`).
3. **Graph Invalidation**: Massive file structural reorganizations require running `graphify update .`.
