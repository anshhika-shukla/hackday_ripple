# Graph Report - ripple  (2026-10-25)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 426 nodes · 955 edges · 22 communities (9 shown, 13 thin omitted)
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 96 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `9ec22a79`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Community 0
- Community 1
- Community 2
- Community 3
- Community 4
- Community 5
- Community 6
- Community 7
- Community 8
- Community 9
- Community 10
- Community 11
- Community 12
- Community 13
- Community 15
- Community 16
- Community 18

## God Nodes (most connected - your core abstractions)
1. `ChangedSymbol` - 38 edges
2. `compute_impact()` - 33 edges
3. `OllamaClient` - 28 edges
4. `load_graph()` - 25 edges
5. `parse_diff()` - 23 edges
6. `select_and_rank_tests()` - 22 edges
7. `CodeGraph` - 20 edges
8. `build_ripple_map_html()` - 16 edges
9. `evaluate_strategy()` - 16 edges
10. `generate_mutants()` - 15 edges

## Surprising Connections (you probably didn't know these)
- `get_mini_app_graph()` --uses--> `CodeGraph`  [INFERRED]
  tests/test_impact.py → src/ripple/graphio.py
- `changed_symbols_for_mutant()` --uses--> `ChangedSymbol`  [INFERRED]
  eval/evaluate.py → src/ripple/diffmap.py
- `filename_heuristic()` --uses--> `ChangedSymbol`  [INFERRED]
  eval/evaluate.py → src/ripple/diffmap.py
- `test_find_uncovered_symbols()` --uses--> `ChangedSymbol`  [INFERRED]
  tests/test_draft.py → src/ripple/diffmap.py
- `test_depth_limit_respected()` --uses--> `ChangedSymbol`  [INFERRED]
  tests/test_impact.py → src/ripple/diffmap.py

## Import Cycles
- None detected.

## Communities (22 total, 13 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.06
Nodes (24): find_uncovered_symbols(), CodeGraph, same_file(), Edge, load_graph(), Node, _node_kind(), normalize_path() (+16 more)

### Community 1 - "Community 1"
Cohesion: 0.06
Nodes (25): ChangedSymbol, draft_pytest_code(), baseline_ranking_b(), OllamaClient, strip_think_blocks(), Rank, rank_candidates(), reciprocal_rank_fusion() (+17 more)

### Community 2 - "Community 2"
Cohesion: 0.06
Nodes (15): smoke_test(), strip_think_blocks(), RippleConfig, verify_drafted_test_on_baseline(), generate_brief(), Report, _triage_line(), count_suite_tests() (+7 more)

### Community 3 - "Community 3"
Cohesion: 0.07
Nodes (15): collect_test_ids(), covered_lines(), find_source_files(), main(), _pytest_env(), run_ground_truth(), run_pytest_suite(), ASTMutator (+7 more)

### Community 4 - "Community 4"
Cohesion: 0.08
Nodes (23): find_graph_file(), get_diff_text(), handle_check(), handle_draft_tests(), handle_install_hook(), handle_select(), main(), _find_enclosing_symbol() (+15 more)

### Community 5 - "Community 5"
Cohesion: 0.10
Nodes (16): Cart, process_order(), check_stock(), reserve_item(), apply_discount(), calculate_tax(), get_final_price(), test_cart_add_item() (+8 more)

### Community 6 - "Community 6"
Cohesion: 0.15
Nodes (9): base_test_id(), changed_symbols_for_mutant(), compute_metrics(), caught_within(), evaluate_strategy(), filename_heuristic(), main(), build_parser() (+1 more)

### Community 7 - "Community 7"
Cohesion: 0.17
Nodes (8): get_mini_app_graph(), test_depth_limit_respected(), test_distance_and_direct_flag(), test_exact_candidates_on_mini_app(), test_import_closure_adds_tests_when_call_edge_missing(), test_ranking_B_puts_direct_tests_first(), test_unchanged_graph_node_yields_no_candidates(), test_unknown_direction_marks_over_approx()

### Community 9 - "Community 9"
Cohesion: 0.29
Nodes (3): find_free_port(), Handler, main()

## Knowledge Gaps
- **2 isolated node(s):** `PYTEST_ADDOPTS`, `ripple`
  These have ≤1 connection - possible missing edges. (Counts symbols only; 182 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **13 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ChangedSymbol` connect `Community 1` to `Community 0`, `Community 4`, `Community 6`, `Community 7`?**
  _High betweenness centrality (0.087) - this node is a cross-community bridge._
- **Are the 31 inferred relationships involving `ChangedSymbol` (e.g. with `changed_symbols_for_mutant()` and `filename_heuristic()`) actually correct?**
  _`ChangedSymbol` has 31 INFERRED edges - model-reasoned connections that need verification._
- **What connects `PYTEST_ADDOPTS`, `ripple` to the rest of the system?**
  _2 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.060528559249786874 - nodes in this community are weakly interconnected._
- **Why does `parse_diff()` connect `Community 4` to `Community 0`, `Community 1`, `Community 2`?**
  _High betweenness centrality (0.061) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `compute_impact()` (e.g. with `ChangedSymbol` and `CodeGraph`) actually correct?**
  _`compute_impact()` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.060153776571687016 - nodes in this community are weakly interconnected._