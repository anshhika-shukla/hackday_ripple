"""Build results.html: a judge-facing page with one tab per evaluated library.

Every number comes from files written by real runs:
- eval/results/<target>/strategy_*.json   (scripts/run_eval.sh)
- eval/data/ground_truth_<target>.json    (planted bugs and the tests that really fail on each)
- eval/results/<target>/demo_report.json  (scripts/demo.sh, optional)

Per-bug rows recompute the SAFE selection (graph + import fallback, no model, no test runs) from the
ground truth, the same way eval/evaluate.py does, and the script stops if the totals do not match
the stored strategy_B.json.
Usage: .venv/bin/python scripts/build_results.py
"""

import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from eval.evaluate import base_test_id, changed_symbols_for_mutant  # noqa: E402
from ripple.graphio import load_graph  # noqa: E402
from ripple.impact import baseline_ranking_b, compute_impact  # noqa: E402

TARGETS = {
    "boltons": {
        "title": "boltons",
        "about": "A widely used Python utility library (boltons 26.2.0).",
    },
    "click": {
        "title": "Click",
        "about": "The Python library behind many command-line tools (pallets/click 8.1.7).",
    },
    "mini_app": {
        "title": "Mini shop app",
        "about": "A tiny shop app we wrote to show the idea end to end.",
    },
}

BUG_KINDS = {
    "CMP_FLIP": "flipped a comparison",
    "ARITH": "changed the arithmetic",
    "CONST_OFF_BY_ONE": "changed a number by one",
    "BOOL_NEGATE": "reversed a condition",
    "RETURN_NONE": "made it return nothing",
}


def changed_lines(diff: str) -> tuple[str, str]:
    """The removed and added code line of a one-line planted bug."""
    before = next((l[1:] for l in diff.splitlines() if l.startswith("-") and not l.startswith("---")), "")
    after = next((l[1:] for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++")), "")
    return before.strip(), after.strip()


def build_target(name: str) -> dict | None:
    gt_path = ROOT / "eval" / "data" / f"ground_truth_{name}.json"
    res_dir = ROOT / "eval" / "results" / name
    graph_path = ROOT / "targets" / name / "graphify-out" / "graph.json"
    if not gt_path.exists() or not (res_dir / "strategy_B.json").exists() or not graph_path.exists():
        print(f"skip {name}: missing ground truth, results or graph")
        return None

    strategies = {k: json.loads((res_dir / f"strategy_{k}.json").read_text())["aggregated"]
                  for k in ("A", "B_graph_only", "B", "C") if (res_dir / f"strategy_{k}.json").exists()}
    stored = json.loads((res_dir / "strategy_B.json").read_text())

    gt = json.loads(gt_path.read_text())
    mutants = gt["mutants"][: stored["n_mutants"]]
    repo = ROOT / "targets" / name
    suite_size = len({base_test_id(t) for t in gt["all_test_ids"]})
    graph = load_graph(graph_path)

    bugs, ratios = [], []
    for m in mutants:
        if not m["killed"] or not m["failed_test_ids"]:
            continue
        changed = changed_symbols_for_mutant(repo, m)
        candidates, _ = compute_impact(graph, changed, max_depth=3, include_import_closure=True)
        selected = [c.test_id for c in baseline_ranking_b(candidates)]
        failed = {base_test_id(t) for t in m["failed_test_ids"]}
        catcher = next((t for t in selected if base_test_id(t) in failed), None)
        before, after = changed_lines(m.get("diff", ""))
        ratios.append(len(selected) / suite_size)
        bugs.append({
            "id": m["mutant_id"],
            "file": m["file"],
            # A bug outside any function maps to the module itself; say so in plain words.
            "function": "top-level code" if changed[0].kind == "module" else changed[0].qualname,
            "kind": BUG_KINDS.get(m["operator"], m["operator"]),
            "before": before,
            "after": after,
            "tests_run": len(selected),
            "tests_failing": len(failed),
            "caught": catcher is not None,
            "caught_by": catcher,
        })

    caught = sum(b["caught"] for b in bugs)
    catch_rate = round(100 * caught / len(bugs), 1)
    ratio = round(100 * statistics.mean(ratios), 1)
    agg = stored["aggregated"]
    if (caught, catch_rate, ratio) != (agg["caught_count"], agg["catch_rate"], agg["mean_selection_ratio"]):
        sys.exit(f"{name}: recomputed {caught} caught / {catch_rate}% / {ratio}% does not match "
                 f"strategy_B.json {agg['caught_count']} / {agg['catch_rate']}% / {agg['mean_selection_ratio']}%")

    demo_path = res_dir / "demo_report.json"
    demo = json.loads(demo_path.read_text()) if demo_path.exists() else None
    if demo:
        patch = ROOT / "scripts" / "bugs" / f"{name}_demo.patch"
        demo["before"], demo["after"] = changed_lines(patch.read_text()) if patch.exists() else ("", "")
        demo["map"] = f"eval/results/{name}/demo_map.html" if (res_dir / "demo_map.html").exists() else None

    return {
        **TARGETS[name],
        "key": name,
        "suite_size": suite_size,
        "planted": len(mutants),
        "bugs": bugs,
        "caught": caught,
        "catch_rate": catch_rate,
        "tests_run_pct": ratio,
        "tests_run_avg": round(statistics.mean(b["tests_run"] for b in bugs)),
        "strategies": strategies,
        "model_runs": json.loads((res_dir / "strategy_C.json").read_text())["runs"] if "C" in strategies else 0,
        "demo": demo,
    }


def main() -> int:
    data = [d for d in (build_target(n) for n in TARGETS) if d]
    template = (ROOT / "scripts" / "results_template.html").read_text(encoding="utf-8")
    payload = json.dumps(data, indent=1).replace("</", "<\\/")
    out = ROOT / "results.html"
    out.write_text(template.replace("/*RESULTS_DATA*/[]", payload), encoding="utf-8")
    for d in data:
        print(f"{d['key']}: {d['caught']}/{len(d['bugs'])} caught ({d['catch_rate']}%), "
              f"{d['tests_run_pct']}% of tests run, demo={'yes' if d['demo'] else 'no'}")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
