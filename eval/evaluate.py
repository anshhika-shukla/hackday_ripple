"""Benchmark scorer: evaluates test selection strategies A, B, and C against ground truth."""

import argparse
import json
import re
import statistics
from pathlib import Path
from typing import Any

from ripple.diffmap import ChangedSymbol, _find_enclosing_symbol, _get_symbols_from_source
from ripple.graphio import load_graph
from ripple.impact import baseline_ranking_b, compute_impact
from ripple.llm import OllamaClient
from ripple.triage import select_and_rank_tests


def base_test_id(test_id: str) -> str:
    """Drop pytest parametrization so tests/x.py::test_y[1] matches the graph's tests/x.py::test_y."""
    return re.sub(r"\[.*\]$", "", test_id)


def changed_symbols_for_mutant(repo: Path, mutant: dict[str, Any]) -> list[ChangedSymbol]:
    """Map the mutated line to its enclosing function, as diffmap does for a real git diff."""
    source = (repo / mutant["file"]).read_text(encoding="utf-8")
    symbol = _find_enclosing_symbol(mutant["line"], _get_symbols_from_source(source, mutant["file"]))
    if symbol is None:
        return [ChangedSymbol(file=mutant["file"], qualname=Path(mutant["file"]).stem, kind="module", changed_lines=[mutant["line"]])]
    return [ChangedSymbol(file=mutant["file"], qualname=symbol["qualname"], kind=symbol["kind"], changed_lines=[mutant["line"]])]


def filename_heuristic(all_test_ids: list[str], changed: list[ChangedSymbol]) -> list[str]:
    """Strategy A: every test in tests/test_<module>.py for each changed module (no graph)."""
    stems = {Path(s.file).stem for s in changed}
    selected: list[str] = []
    for test_id in all_test_ids:
        file_stem = Path(test_id.split("::")[0]).stem
        if any(file_stem in (f"test_{stem}", f"{stem}_test") for stem in stems):
            base = base_test_id(test_id)
            if base not in selected:
                selected.append(base)
    return selected


def compute_metrics(
    selected_tests_by_mutant: list[list[str]],
    ground_truth_mutants: list[dict[str, Any]],
    total_suite_size: int = 150,
) -> dict[str, float]:
    """Calculate catch-rate, selection ratio, and recall@K."""
    killed_count = 0
    caught_count = 0
    caught_at_3 = 0
    caught_at_5 = 0
    caught_at_10 = 0
    selection_ratios = []

    for selected, gt in zip(selected_tests_by_mutant, ground_truth_mutants):
        if not gt["killed"] or not gt["failed_test_ids"]:
            continue

        killed_count += 1
        failed_set = {base_test_id(t) for t in gt["failed_test_ids"]}

        def caught_within(tests: list[str]) -> bool:
            return any(base_test_id(t) in failed_set for t in tests)

        if caught_within(selected):
            caught_count += 1
        if caught_within(selected[:3]):
            caught_at_3 += 1
        if caught_within(selected[:5]):
            caught_at_5 += 1
        if caught_within(selected[:10]):
            caught_at_10 += 1

        selection_ratios.append(len(selected) / max(total_suite_size, 1))

    catch_rate = (caught_count / killed_count) if killed_count else 0.0
    r3 = (caught_at_3 / killed_count) if killed_count else 0.0
    r5 = (caught_at_5 / killed_count) if killed_count else 0.0
    r10 = (caught_at_10 / killed_count) if killed_count else 0.0
    mean_ratio = statistics.mean(selection_ratios) if selection_ratios else 0.0

    return {
        "killed_count": killed_count,
        "caught_count": caught_count,
        "catch_rate": round(catch_rate * 100, 1),
        "mean_selection_ratio": round(mean_ratio * 100, 1),
        "recall_at_3": round(r3 * 100, 1),
        "recall_at_5": round(r5 * 100, 1),
        "recall_at_10": round(r10 * 100, 1),
    }


def evaluate_strategy(
    strategy: str,
    ground_truth_path: Path,
    graph_path: Path,
    n_mutants: int = 30,
    runs: int = 1,
    use_cache: bool = True,
    out_dir: Path = Path("eval/results"),
    import_closure: bool = True,
) -> dict[str, Any]:
    """Execute evaluation benchmark for strategy A, B, or C."""
    gt_data = json.loads(ground_truth_path.read_text(encoding="utf-8"))
    mutants = gt_data["mutants"][:n_mutants]
    repo = Path(gt_data["target_repo"])
    if not repo.exists():  # ground truth recorded in another checkout: use this one's targets/
        repo = Path("targets") / repo.name
    all_test_ids = gt_data["all_test_ids"]
    # Selection ratio is measured against unique test functions, the unit RIPPLE selects.
    suite_size = len({base_test_id(t) for t in all_test_ids})
    graph = load_graph(graph_path)
    client = OllamaClient()

    run_results = []
    out_dir.mkdir(parents=True, exist_ok=True)

    for run_idx in range(runs):
        selected_for_mutants = []

        for m in mutants:
            diff_text = m.get("diff", "")
            changed_syms = changed_symbols_for_mutant(repo, m)

            if strategy == "A":
                selected_for_mutants.append(filename_heuristic(all_test_ids, changed_syms))

            elif strategy == "B":
                candidates, _ = compute_impact(graph, changed_syms, max_depth=3, include_import_closure=import_closure)
                selected_for_mutants.append([c.test_id for c in baseline_ranking_b(candidates)])

            elif strategy == "C":
                selected, _, _, _ = select_and_rank_tests(
                    graph=graph,
                    changed_symbols=changed_syms,
                    diff_text=diff_text,
                    client=client,
                    mode="safe",
                    use_cache=use_cache,
                )
                selected_for_mutants.append([c.test_id for c in selected])

        metrics = compute_metrics(selected_for_mutants, mutants, total_suite_size=suite_size)
        run_results.append(metrics)

    summary = {
        "strategy": strategy,
        "import_closure": import_closure if strategy == "B" else None,
        "model": client.model if strategy == "C" else None,
        "tokens_per_sec": round(statistics.mean(client.token_rates), 2) if client.token_rates else None,
        "suite_size": suite_size,
        "n_mutants": len(mutants),
        "runs": runs,
        "metrics_per_run": run_results,
        "aggregated": run_results[0] if runs == 1 else {
            k: round(statistics.mean([r[k] for r in run_results]), 1)
            for k in run_results[0]
        },
    }

    # Save JSON and Markdown
    name = f"{strategy}_graph_only" if strategy == "B" and not import_closure else strategy
    json_path = out_dir / f"strategy_{name}.json"
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    md_content = f"""# Strategy {strategy} Evaluation Results

- **Strategy**: {strategy}
- **Mutants Evaluated**: {len(mutants)}
- **Runs**: {runs}
- **Catch Rate**: {summary['aggregated']['catch_rate']}%
- **Selection Ratio**: {summary['aggregated']['mean_selection_ratio']}%
- **recall@3**: {summary['aggregated']['recall_at_3']}%
- **recall@5**: {summary['aggregated']['recall_at_5']}%
- **recall@10**: {summary['aggregated']['recall_at_10']}%
"""
    (out_dir / f"strategy_{name}.md").write_text(md_content, encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description="Evaluate test selection strategies.")
    parser.add_argument("--strategy", choices=["A", "B", "C"], default="B", help="Selection strategy")
    parser.add_argument("--mutants", type=int, default=30, help="Number of mutants to evaluate")
    parser.add_argument("--runs", type=int, default=1, help="Number of benchmark runs")
    parser.add_argument("--no-cache", action="store_true", help="Bypass LLM response cache")
    parser.add_argument("--gt", default="eval/data/ground_truth_click.json", help="Ground truth JSON path")
    parser.add_argument("--graph", default="targets/click/graphify-out/graph.json", help="Graphify graph.json path")
    parser.add_argument("--no-closure", action="store_true", help="Strategy B without the import-closure fallback")
    parser.add_argument("--out-dir", default="eval/results", help="Where to write strategy_<X>.json/.md")
    args = parser.parse_args()

    res = evaluate_strategy(
        strategy=args.strategy,
        ground_truth_path=Path(args.gt),
        graph_path=Path(args.graph),
        n_mutants=args.mutants,
        runs=args.runs,
        use_cache=not args.no_cache,
        out_dir=Path(args.out_dir),
        import_closure=not args.no_closure,
    )
    print(f"Strategy {args.strategy} benchmark complete: catch-rate={res['aggregated']['catch_rate']}%")


if __name__ == "__main__":
    main()
