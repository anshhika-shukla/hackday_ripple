"""Standalone offline HTML page that explains one change: what uses it and which tests ran."""

import argparse
import html
import json
import sys
from collections import deque
from pathlib import Path
from typing import Any

from ripple.diffmap import ChangedSymbol, parse_diff
from ripple.graphio import CodeGraph, load_graph, normalize_path
from ripple.impact import CandidateTest, _ripple_neighbors, compute_impact, is_test_file
from ripple.report import cases_run

CHANGE = "#eb6834"  # orange: the changed code
CALLER = "#898781"  # grey: code on the path between the change and a test
TEST = "#2a78d6"  # blue: a test RIPPLE runs


def _start_nodes(graph: CodeGraph, changed_symbols: list[ChangedSymbol]) -> tuple[list[str], set[str]]:
    """Graph nodes the ripple starts from (same rule as compute_impact) and the resolved changed nodes."""
    starts: list[str] = []
    resolved: set[str] = set()
    for s in changed_symbols:
        nid = s.node_id or graph.find_node(s.file, s.qualname)
        if nid and nid in graph.nodes:
            starts.append(nid)
            resolved.add(nid)
        else:
            norm = normalize_path(s.file)
            for node in graph.nodes.values():
                if node.file and (norm == node.file or norm.endswith("/" + node.file)) and node.kind in ("function", "method", "class"):
                    starts.append(node.id)
    return list(dict.fromkeys(starts)), resolved


def _ripple_tree(graph: CodeGraph, starts: list[str], max_depth: int) -> tuple[dict[str, int], dict[str, str | None]]:
    """BFS over the relations compute_impact follows; returns distance and BFS parent of each reached node."""
    dist = {n: 0 for n in starts}
    parent: dict[str, str | None] = {n: None for n in starts}
    queue = deque(starts)
    while queue:
        cur = queue.popleft()
        if dist[cur] >= max_depth:
            continue
        for nbr in _ripple_neighbors(graph, cur):
            if nbr not in dist:
                dist[nbr] = dist[cur] + 1
                parent[nbr] = cur
                queue.append(nbr)
    return dist, parent


def _names(items: list[str], cap: int) -> str:
    """Chips for up to `cap` names, then a '+N more' chip."""
    chips = "".join(f'<span class="chip">{html.escape(n)}</span>' for n in items[:cap])
    if len(items) > cap:
        chips += f'<span class="chip more">+{len(items) - cap} more</span>'
    return chips


def build_ripple_map_html(
    graph: CodeGraph,
    changed_symbols: list[ChangedSymbol],
    selected_tests: list[CandidateTest],
    total_suite_count: int,
    report: dict[str, Any] | None = None,
    max_depth: int = 3,
    max_files: int = 12,
) -> str:
    """Generate a standalone offline HTML page that explains one change as a left-to-right story.

    1. your change, 2. the code that uses it (by number of steps away in the Graphify graph),
    3. the test files RIPPLE ran: tests found by following the code vs. tests run to be safe
    (the file imports the changed code). With a ripple report, the failing tests are marked.
    """
    report = report or {}
    failed_ids = set(report.get("results", {}).get("failed_ids", []))

    # Step 2: code that uses the change, grouped by how many steps away it is.
    starts, _ = _start_nodes(graph, changed_symbols)
    dist, _ = _ripple_tree(graph, starts, max_depth)
    by_step: dict[int, list[str]] = {}
    for n, d in sorted(dist.items(), key=lambda kv: (kv[1], graph.nodes[kv[0]].name)):
        node = graph.nodes[n]
        if d == 0 or node.kind == "module" or is_test_file(node.file):
            continue
        names = by_step.setdefault(d, [])
        if node.name not in names:
            names.append(node.name)

    # Step 3: test files, with tests found via the code (graph) and tests run to be safe (import fallback).
    files: dict[str, dict[str, list[CandidateTest]]] = {}
    for c in selected_tests:
        files.setdefault(c.file, {"graph": [], "safe": []})["graph" if c.source == "graph" else "safe"].append(c)
    n_graph = sum(len(f["graph"]) for f in files.values())
    n_safe = sum(len(f["safe"]) for f in files.values())

    def failed_in(f: dict[str, list[CandidateTest]]) -> list[str]:
        return [c.test_id for c in f["graph"] + f["safe"] if c.test_id in failed_ids]

    ordered = sorted(files.items(), key=lambda kv: (-len(failed_in(kv[1])), -len(kv[1]["graph"]), -len(kv[1]["safe"]), kv[0]))
    biggest = max((len(f["graph"]) + len(f["safe"]) for f in files.values()), default=1)

    cards = []
    for file, f in ordered[:max_files]:
        g, s, failed = len(f["graph"]), len(f["safe"]), failed_in(f)
        parts = []
        if g:
            parts.append(f"<strong>{g}</strong> found by following the code")
        if s:
            parts.append(f"{s} run to be safe")
        found = "".join(
            f'<li><code>{html.escape(c.test_id.split("::", 1)[-1])}</code>'
            f'<span class="via">via {html.escape(" › ".join(c.via[1:-1]) or "a direct call")}</span></li>'
            for c in f["graph"]
        )
        caught = "".join(f'<div class="caught">✗ <code>{html.escape(t.split("::", 1)[-1])}</code> failed: this test caught the bug</div>' for t in failed)
        cards.append(
            f'<div class="file{" hit" if failed else ""}"><div class="fname">{html.escape(file)}</div>'
            f'<div class="bar" title="{g} found by following the code, {s} run to be safe">'
            f'<i class="seg g" style="width:{100 * g / biggest:.1f}%"></i><i class="seg s" style="width:{100 * s / biggest:.1f}%"></i></div>'
            f'<div class="counts">{" · ".join(parts)}</div>{caught}'
            + (f'<details><summary>Show the {g} test{"s" if g != 1 else ""} found by following the code</summary><ul>{found}</ul></details>' if g else "")
            + "</div>"
        )
    if len(ordered) > max_files:
        rest = ordered[max_files:]
        cards.append(f'<div class="file rest">… and {len(rest)} more test files ({sum(len(f["graph"]) + len(f["safe"]) for _, f in rest)} tests), all run to be safe.</div>')
    if not cards:
        cards.append('<div class="file rest">No tests reach this change.</div>')

    steps_html = "".join(
        f'<div class="step-row"><div class="step-k">{d} step{"s" if d != 1 else ""} away</div><div>{_names(names, 10)}</div></div>'
        for d, names in sorted(by_step.items())
    ) or '<p class="muted">Nothing else in the code map uses it, so RIPPLE goes straight to the tests.</p>'

    changed_boxes = "".join(
        f'<div class="changed-box"><code>{html.escape(s.qualname)}</code><div class="muted">{html.escape(s.file)}</div></div>'
        for s in changed_symbols
    ) or '<p class="muted">No code change found.</p>'

    # Header in plain words: what changed, how many tests ran, what happened, and the AI's read.
    first = changed_symbols[0].qualname if changed_symbols else "nothing"
    n_selected = report.get("selected", len(selected_tests))
    results = report.get("results") or {}
    # Picked tests are test functions; the suite total is pytest test cases (parametrized functions expand).
    ran = cases_run(results)
    if ran and total_suite_count:
        scope = f"pytest ran {ran} of {total_suite_count} test cases ({100 * ran / total_suite_count:.1f}%)"
    else:
        scope = f"{total_suite_count} test cases in the suite" if total_suite_count else ""
    stats = [f'<div class="stat"><span class="k">Tests RIPPLE picked</span><span class="v"><strong>{n_selected}</strong> test functions</span><span class="d">{scope}</span></div>']
    if results:
        n_fail = results.get("failed", 0)
        verdict = f'<span class="v caught-v">✓ Bug caught</span><span class="d">{n_fail} test{"s" if n_fail != 1 else ""} failed, {results.get("passed", 0)} passed</span>' if n_fail \
            else f'<span class="v">No test failed</span><span class="d">{results.get("passed", 0)} passed</span>'
        stats.append(f'<div class="stat"><span class="k">Result</span>{verdict}</div>')
    timing = report.get("timing") or {}
    if timing:
        parts = [f"{label} {timing[key]:.2f} s" for key, label in (("graph_s", "finding tests"), ("llm_s", "AI"), ("tests_s", "running them"), ("full_suite_s", "all tests")) if key in timing]
        stats.append(f'<div class="stat"><span class="k">Time</span><span class="v small">{" · ".join(parts)}</span></div>')

    model_line = ""
    if report:
        status = report.get("llm_status")
        triage = report.get("triage") or {}
        if status == "ok" and triage:
            model_line = f'<strong>Risk {triage.get("risk")}/5.</strong> {html.escape(str(triage.get("summary", "")))}'
        elif status == "fallback":
            model_line = "The AI was unavailable, so tests were ordered by the code map only."
        elif status == "skipped_deterministic":
            model_line = "Not needed: only comments or docstrings changed."
        else:
            model_line = "AI turned off (--no-llm); tests ordered by the code map only."
        model_line = f'<div class="model"><span class="k">The AI\'s read</span> {model_line}</div>'

    summary = (
        f"RIPPLE followed the code from <code>{html.escape(first)}</code> to <strong>{n_graph}</strong> test{'s' if n_graph != 1 else ''}"
        + (f", and ran <strong>{n_safe}</strong> more from files that import the changed code, to be safe" if n_safe else "")
        + "."
    )
    if failed_ids:
        summary += f" <strong>{len(failed_ids)}</strong> failed, so the bug was caught before it shipped."
    elif results:
        summary += " None failed."

    dark = "--page: #0d0d0d; --surface: #1a1a19; --ink: #f0efec; --ink-2: #c3c2b7; --grid: #2c2c2a; --border: rgba(255,255,255,0.10); --code-bg: #262624; --test: #3987e5; --change: #d95926; --other: #52514e;"
    html_page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>RIPPLE Change Story</title>
  <style>
    :root {{ color-scheme: light; --page: #f9f9f7; --surface: #ffffff; --ink: #0b0b0b; --ink-2: #52514e; --grid: #e1e0d9; --border: rgba(11,11,11,0.10); --code-bg: #f0efec; --test: {TEST}; --change: {CHANGE}; --other: #c3c2b7; }}
    @media (prefers-color-scheme: dark) {{ :root:where(:not([data-theme="light"])) {{ color-scheme: dark; {dark} }} }}
    :root[data-theme="dark"] {{ color-scheme: dark; {dark} }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; padding: 20px 16px 40px; background: var(--page); color: var(--ink); font: 16px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }}
    .wrap {{ max-width: 1200px; margin: 0 auto; }}
    h1 {{ margin: 0 0 4px; font-size: 24px; }}
    h1 span {{ color: var(--test); }}
    code {{ font-family: ui-monospace, monospace; background: var(--code-bg); padding: 1px 6px; border-radius: 4px; overflow-wrap: anywhere; }}
    .stats {{ display: flex; flex-wrap: wrap; gap: 12px; margin: 12px 0 10px; }}
    .stat {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 8px 14px; display: flex; flex-direction: column; gap: 2px; }}
    .k {{ font-size: 13px; color: var(--ink-2); }}
    .v {{ font-size: 20px; }}
    .v.small {{ font-size: 15px; padding-top: 4px; }}
    .caught-v {{ color: var(--test); font-weight: 700; }}
    .d, .muted {{ font-size: 14px; color: var(--ink-2); }}
    .model {{ font-size: 15px; margin-bottom: 8px; line-height: 1.45; }}
    .model .k {{ margin-right: 6px; }}
    .summary {{ font-size: 19px; margin: 14px 0 16px; max-width: 1000px; }}
    .story {{ display: grid; grid-template-columns: minmax(180px, 1fr) 28px minmax(220px, 1.4fr) 28px minmax(300px, 2.2fr); gap: 8px; align-items: start; }}
    .col {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 14px 16px; }}
    .col h2 {{ margin: 0 0 10px; font-size: 16px; }}
    .col h2 i {{ display: inline-block; width: 12px; height: 12px; border-radius: 50%; margin-right: 8px; vertical-align: -1px; }}
    .arrow {{ margin-top: 48px; text-align: center; font-size: 26px; color: var(--ink-2); }}
    .changed-box {{ border: 2px solid var(--change); border-radius: 10px; padding: 10px 12px; margin-bottom: 8px; }}
    .changed-box code {{ font-size: 16px; font-weight: 600; background: none; padding: 0; }}
    .step-row {{ margin-bottom: 10px; }}
    .step-k {{ font-size: 13px; color: var(--ink-2); margin-bottom: 4px; }}
    .chip {{ display: inline-block; font: 13px ui-monospace, monospace; background: var(--code-bg); border-radius: 999px; padding: 2px 9px; margin: 0 4px 4px 0; }}
    .chip.more {{ font-family: system-ui, sans-serif; color: var(--ink-2); }}
    .file {{ border: 1px solid var(--border); border-radius: 10px; padding: 10px 12px; margin-bottom: 8px; }}
    .file.hit {{ border: 2px solid var(--change); }}
    .file.rest {{ color: var(--ink-2); font-size: 14px; }}
    .fname {{ font: 600 15px ui-monospace, monospace; overflow-wrap: anywhere; }}
    .bar {{ display: flex; gap: 2px; height: 10px; margin: 6px 0 4px; }}
    .seg {{ display: block; height: 100%; border-radius: 3px; }}
    .seg.g {{ background: var(--test); }}
    .seg.s {{ background: var(--other); }}
    .counts {{ font-size: 14px; color: var(--ink-2); }}
    .caught {{ margin-top: 6px; font-size: 14px; color: var(--change); font-weight: 600; }}
    details {{ margin-top: 6px; font-size: 14px; }}
    summary {{ cursor: pointer; color: var(--ink-2); }}
    ul {{ margin: 6px 0 0; padding-left: 18px; }}
    li {{ margin-bottom: 3px; }}
    .via {{ color: var(--ink-2); margin-left: 6px; font-size: 13px; }}
    .legend {{ display: flex; flex-wrap: wrap; gap: 18px; font-size: 14px; color: var(--ink-2); margin: 0 0 10px; }}
    .legend i {{ display: inline-block; width: 22px; height: 10px; border-radius: 3px; margin-right: 6px; vertical-align: 0; }}
    .note {{ font-size: 14px; color: var(--ink-2); margin-top: 14px; max-width: 1000px; }}
    @media (max-width: 900px) {{ .story {{ grid-template-columns: 1fr; }} .arrow {{ transform: rotate(90deg); }} }}
  </style>
</head>
<body>
<div class="wrap">
  <h1><span>RIPPLE</span> · what your change could break</h1>
  <div class="stats">{"".join(stats)}</div>
  {model_line}
  <p class="summary">{summary}</p>
  <div class="story">
    <div class="col"><h2><i style="background:var(--change)"></i>1 · Your change</h2>{changed_boxes}</div>
    <div class="arrow">→</div>
    <div class="col"><h2><i style="background:{CALLER}"></i>2 · Code that uses it</h2>{steps_html}</div>
    <div class="arrow">→</div>
    <div class="col"><h2><i style="background:var(--test)"></i>3 · Test files RIPPLE ran</h2>
      <div class="legend"><span><i style="background:var(--test)"></i>found by following the code</span><span><i style="background:var(--other)"></i>run to be safe</span></div>
      {"".join(cards)}
    </div>
  </div>
  <p class="note">How RIPPLE chose: it starts at your change and follows Graphify's code map to everything that uses it, up to {max_depth} steps away. Tests reached that way are “found by following the code”. A map read from the source can miss links made while the program runs, so RIPPLE also runs every test file that imports the changed file (“run to be safe”). The AI never removes tests.</p>
</div>
</body>
</html>
"""
    return html_page


def generate_map_cli(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    from ripple.cli import find_graph_file, get_diff_text
    from ripple.runner import count_suite_tests
    diff_text = get_diff_text(repo)
    changed_symbols = parse_diff(repo=repo, patch_text=diff_text if diff_text else None)

    graph_path = find_graph_file(repo, args.graph)
    if not graph_path:
        print("Error: graph.json not found.", file=sys.stderr)
        return 2

    report = json.loads(Path(args.report).read_text(encoding="utf-8")) if args.report else None
    graph = load_graph(graph_path)
    candidates, _ = compute_impact(graph, changed_symbols)
    html_content = build_ripple_map_html(
        graph=graph,
        changed_symbols=changed_symbols,
        selected_tests=candidates,
        total_suite_count=report["suite_total"] if report else count_suite_tests(repo),
        report=report,
    )

    out_file = Path(args.out)
    out_file.write_text(html_content, encoding="utf-8")
    print(f"✅ RIPPLE map written to {out_file.resolve()}")
    return 0
