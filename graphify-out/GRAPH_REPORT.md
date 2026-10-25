# Graph Report - ripple  (2026-10-25)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 564 nodes · 1191 edges · 30 communities (16 shown, 14 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 97 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `4ca011d1`
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
- Community 14
- Community 15
- Community 16
- Community 17
- Community 18
- Community 20
- Community 21
- Community 23
- Community 24
- Community 25
- Community 26
- Community 27
- Community 29

## God Nodes (most connected - your core abstractions)
1. `ChangedSymbol` - 35 edges
2. `compute_impact()` - 31 edges
3. `OllamaClient` - 28 edges
4. `load_graph()` - 23 edges
5. `parse_diff()` - 23 edges
6. `CodeGraph` - 22 edges
7. `select_and_rank_tests()` - 22 edges
8. `evaluate_strategy()` - 16 edges
9. `handle_check()` - 15 edges
10. `generate_mutants()` - 15 edges

## Surprising Connections (you probably didn't know these)
- `test_draft_pytest_syntax_validation()` --uses--> `ChangedSymbol`  [INFERRED]
  tests/test_draft.py → src/ripple/diffmap.py
- `test_find_uncovered_symbols()` --uses--> `ChangedSymbol`  [INFERRED]
  tests/test_draft.py → src/ripple/diffmap.py
- `test_records_tokens_per_sec()` --uses--> `ChangedSymbol`  [INFERRED]
  tests/test_llm_live.py → src/ripple/diffmap.py
- `test_schema_valid_rate_on_20_sample_diffs()` --uses--> `ChangedSymbol`  [INFERRED]
  tests/test_llm_live.py → src/ripple/diffmap.py
- `test_budget_mode_returns_exactly_k_by_fused_rank()` --uses--> `ChangedSymbol`  [INFERRED]
  tests/test_triage.py → src/ripple/diffmap.py

## Import Cycles
- None detected.

## Communities (30 total, 14 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.06
Nodes (29): build_parser(), find_graph_file(), get_diff_text(), handle_check(), handle_draft_tests(), handle_install_hook(), handle_select(), main() (+21 more)

### Community 1 - "Community 1"
Cohesion: 0.07
Nodes (15): collect_test_ids(), covered_lines(), find_source_files(), main(), _pytest_env(), run_ground_truth(), run_pytest_suite(), ASTMutator (+7 more)

### Community 2 - "Community 2"
Cohesion: 0.07
Nodes (10): find_free_port(), Handler, main(), smoke_test(), strip_think_blocks(), RippleConfig, strip_think_blocks(), run_tests() (+2 more)

### Community 3 - "Community 3"
Cohesion: 0.08
Nodes (27): get_item(), price_of(), veg_items(), format_rupees(), percent_of(), round_to_rupee(), gst(), line_total() (+19 more)

### Community 4 - "Community 4"
Cohesion: 0.10
Nodes (16): Cart, process_order(), check_stock(), reserve_item(), apply_discount(), calculate_tax(), get_final_price(), test_cart_add_item() (+8 more)

### Community 5 - "Community 5"
Cohesion: 0.08
Nodes (13): ASTSymbolCollector, _find_enclosing_symbol(), _get_symbols_from_source(), main(), _normalize_ast_for_comparison(), _strip_docstring(), _page(), test_code_that_uses_the_change_is_shown() (+5 more)

### Community 6 - "Community 6"
Cohesion: 0.10
Nodes (16): baseline_ranking_b(), CandidateTest, Rank, rank_candidates(), reciprocal_rank_fusion(), select_and_rank_tests(), Triage, test_budget_mode_returns_exactly_k_by_fused_rank() (+8 more)

### Community 7 - "Community 7"
Cohesion: 0.11
Nodes (11): CodeGraph, same_file(), Node, normalize_path(), baseline_ranking_a(), files_importing(), is_runnable_test(), is_test_file() (+3 more)

### Community 8 - "Community 8"
Cohesion: 0.14
Nodes (11): base_test_id(), changed_symbols_for_mutant(), compute_metrics(), caught_within(), evaluate_strategy(), filename_heuristic(), main(), build_target() (+3 more)

### Community 9 - "Community 9"
Cohesion: 0.10
Nodes (5): test_add_unknown_item_leaves_cart_unchanged(), test_add_zero_quantity_rejected(), test_line_total_rejects_zero_quantity(), test_line_total_unknown_item(), mini_app_repo()

### Community 10 - "Community 10"
Cohesion: 0.17
Nodes (16): points_for(), redeem_value(), place_order(), receipt(), test_no_points_below_twenty_rupees(), test_one_point_per_twenty_rupees(), test_redeem_capped_at_bill(), test_redeem_negative_points() (+8 more)

### Community 11 - "Community 11"
Cohesion: 0.19
Nodes (10): ChangedSymbol, compute_impact(), get_mini_app_graph(), test_depth_limit_respected(), test_distance_and_direct_flag(), test_exact_candidates_on_mini_app(), test_import_closure_adds_tests_when_call_edge_missing(), test_ranking_B_puts_direct_tests_first() (+2 more)

### Community 12 - "Community 12"
Cohesion: 0.15
Nodes (4): OllamaClient, triage_change(), test_records_tokens_per_sec(), test_schema_valid_rate_on_20_sample_diffs()

### Community 13 - "Community 13"
Cohesion: 0.16
Nodes (8): test_added_and_deleted_function(), test_body_change_maps_to_function(), test_comment_only_change_is_ast_equal(), test_docstring_only_change_is_ast_equal(), test_method_in_class_gets_qualified_name(), test_module_level_change(), test_multi_hunk_multi_file(), test_non_python_file_ignored()

### Community 14 - "Community 14"
Cohesion: 0.20
Nodes (4): _ripple_neighbors(), build_ripple_map_html(), _names(), _ripple_tree()

### Community 15 - "Community 15"
Cohesion: 0.20
Nodes (3): test_draft_pytest_syntax_validation(), test_find_uncovered_symbols(), test_verify_drafted_test_on_baseline()

## Knowledge Gaps
- **2 isolated node(s):** `PYTEST_ADDOPTS`, `ripple`
  These have ≤1 connection - possible missing edges. (Counts symbols only; 238 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **14 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ChangedSymbol` connect `Community 11` to `Community 0`, `Community 5`, `Community 6`, `Community 7`, `Community 8`, `Community 12`, `Community 14`, `Community 15`, `Community 16`?**
  _High betweenness centrality (0.060) - this node is a cross-community bridge._
- **Are the 24 inferred relationships involving `ChangedSymbol` (e.g. with `draft_pytest_code()` and `find_uncovered_symbols()`) actually correct?**
  _`ChangedSymbol` has 24 INFERRED edges - model-reasoned connections that need verification._
- **What connects `PYTEST_ADDOPTS`, `ripple` to the rest of the system?**
  _2 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.05548654244306418 - nodes in this community are weakly interconnected._
- **Why does `parse_diff()` connect `Community 0` to `Community 13`, `Community 11`, `Community 5`, `Community 14`?**
  _High betweenness centrality (0.040) - this node is a cross-community bridge._
- **Are the 7 inferred relationships involving `compute_impact()` (e.g. with `evaluate_strategy()` and `build_target()`) actually correct?**
  _`compute_impact()` has 7 INFERRED edges - model-reasoned connections that need verification._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.06588235294117648 - nodes in this community are weakly interconnected._