"""Benchmark scorer: evaluates test selection strategies A, B, and C against ground truth."""

import argparse
import json
import statistics
from pathlib import Path
from typing import Any

from ripple.diffmap import ChangedSymbol, parse_diff
from ripple.graphio import load_graph
from ripple.impact import baseline_ranking_a, baseline_ranking_b, compute_impact
from ripple.llm import OllamaClient
from ripple.triage import select_and_rank_tests


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
        failed_set = set(gt["failed_test_ids"])

        # Check intersection
        has_caught = any(
            t in failed_set or any(f in t for f in failed_set) for t in selected
        )
        if has_caught:
            caught_count += 1

        top3 = selected[:3]
        if any(t in failed_set or any(f in t for f in failed_set) for t in top3):
            caught_at_3 += 1

        top5 = selected[:5]
        if any(t in failed_set or any(f in t for f in failed_set) for t in top5):
            caught_at_5 += 1

        top10 = selected[:10]
        if any(t in failed_set or any(f in t for f in failed_set) for t in top10):
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
) -> dict[str, Any]:
    """Execute evaluation benchmark for strategy A, B, or C."""
    gt_data = json.loads(ground_truth_path.read_text(encoding="utf-8"))
    mutants = gt_data["mutants"][:n_mutants]
    graph = load_graph(graph_path) if graph_path.exists() else None
    client = OllamaClient()

    run_results = []
    out_dir.mkdir(parents=True, exist_ok=True)

    for run_idx in range(runs):
        selected_for_mutants = []

        for m in mutants:
            diff_text = m.get("diff", "")
            changed_syms = [
                ChangedSymbol(
                    file=m["file"],
                    qualname=Path(m["file"]).stem,
                    kind="function",
                    ast_equal=False,
                )
            ]

            if strategy == "A":
                # Strategy A: Filename heuristic
                if graph:
                    candidates, _ = compute_impact(graph, changed_syms, max_depth=3)
                    ranked = baseline_ranking_a(candidates, changed_syms)
                    selected_for_mutants.append([c.test_id for c in ranked])
                else:
                    selected_for_mutants.append([])

            elif strategy == "B":
                # Strategy B: Graphify graph only
                if graph:
                    candidates, _ = compute_impact(graph, changed_syms, max_depth=3)
                    ranked = baseline_ranking_b(candidates)
                    selected_for_mutants.append([c.test_id for c in ranked])
                else:
                    selected_for_mutants.append([])

            elif strategy == "C":
                # Strategy C: Graph + Local LLM
                if graph:
                    selected, _, _, _ = select_and_rank_tests(
                        graph=graph,
                        changed_symbols=changed_syms,
                        diff_text=diff_text,
                        client=client,
                        mode="safe",
                        use_cache=use_cache,
                    )
                    selected_for_mutants.append([c.test_id for c in selected])
                else:
                    selected_for_mutants.append([])

        metrics = compute_metrics(selected_for_mutants, mutants)
        run_results.append(metrics)

    summary = {
        "strategy": strategy,
        "n_mutants": len(mutants),
        "runs": runs,
        "metrics_per_run": run_results,
        "aggregated": run_results[0] if runs == 1 else {
            k: round(statistics.mean([r[k] for r in run_results]), 1)
            for k in run_results[0]
        },
    }

    # Save JSON and Markdown
    json_path = out_dir / f"strategy_{strategy}.json"
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
    (out_dir / f"strategy_{strategy}.md").write_text(md_content, encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description="Evaluate test selection strategies.")
    parser.add_argument("--strategy", choices=["A", "B", "C"], default="B", help="Selection strategy")
    parser.add_argument("--mutants", type=int, default=30, help="Number of mutants to evaluate")
    parser.add_argument("--runs", type=int, default=1, help="Number of benchmark runs")
    parser.add_argument("--no-cache", action="store_true", help="Bypass LLM response cache")
    parser.add_argument("--gt", default="eval/data/ground_truth.json", help="Ground truth JSON path")
    parser.add_argument("--graph", default="tests/fixtures/graph.json", help="Graphify graph.json path")
    args = parser.parse_args()

    res = evaluate_strategy(
        strategy=args.strategy,
        ground_truth_path=Path(args.gt),
        graph_path=Path(args.graph),
        n_mutants=args.mutants,
        runs=args.runs,
        use_cache=not args.no_cache,
    )
    print(f"Strategy {args.strategy} benchmark complete: catch-rate={res['aggregated']['catch_rate']}%")


if __name__ == "__main__":
    main()
