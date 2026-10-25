"""Standalone offline HTML/SVG ripple map generator."""

import argparse
import html
import json
import math
import sys
from collections import deque
from pathlib import Path
from typing import Any

from ripple.diffmap import ChangedSymbol, parse_diff
from ripple.graphio import CodeGraph, load_graph, normalize_path
from ripple.impact import CandidateTest, _ripple_neighbors, compute_impact, is_runnable_test, to_pytest_id

CHANGE = "#eb6834"  # orange: the changed code
CALLER = "#898781"  # grey: code on the path between the change and a test
TEST = "#2a78d6"  # blue: a test RIPPLE runs
RING_GAP = 110
MAX_DEAD_END_CALLERS = 24  # callers that lead to no test; enough to show the spread without clutter
LABEL_CHAR_W = 12.5  # approximate width of one character at the SVG label font size, for fitting the viewBox
PILL_CHAR_W = 10.5


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


def _radial_text(x: float, y: float, angle: float, offset: float, inner: str, css_class: str) -> str:
    """Text pointing away from the centre, flipped on the left half so it never reads upside down."""
    deg = math.degrees(angle)
    if math.cos(angle) < -1e-9:
        deg += 180
        anchor, dx = "end", -offset
    else:
        anchor, dx = "start", offset
    return (
        f'<text transform="translate({x:.1f},{y:.1f}) rotate({deg:.1f})" x="{dx:.1f}" dy="0.35em" '
        f'text-anchor="{anchor}" class="{css_class}">{inner}</text>'
    )


def build_ripple_map_html(
    graph: CodeGraph,
    changed_symbols: list[ChangedSymbol],
    selected_tests: list[CandidateTest],
    total_suite_count: int,
    max_nodes: int = 120,
    report: dict[str, Any] | None = None,
    max_depth: int = 3,
) -> str:
    """Generate standalone offline HTML with an inline SVG radial ripple map.

    The changed function sits at the centre, callers on rings by call distance, tests reached through
    the graph in green, and tests chosen by the import fallback as one pill per test file on a dashed
    outer ring. With a ripple report, failed tests are marked and the header shows the run results.
    """
    report = report or {}
    failed_ids = set(report.get("results", {}).get("failed_ids", []))
    selected_ids = {c.test_id for c in selected_tests}

    starts, resolved = _start_nodes(graph, changed_symbols)
    dist, parent = _ripple_tree(graph, starts, max_depth)

    # Choose which nodes to draw: the changed nodes, then paths to graph-reached tests (nearest first),
    # then callers that reach no test. Leave room for up to 5 ring-guide circles within max_nodes.
    node_budget = max_nodes - 5
    drawn: dict[str, None] = dict.fromkeys(n for n in starts if n in resolved)
    test_nodes = sorted(
        (n for n in dist if is_runnable_test(graph, graph.nodes[n]) and to_pytest_id(graph.nodes[n]) in selected_ids),
        key=lambda n: (dist[n], n),
    )
    for t in test_nodes:
        chain, n = [], t
        while n is not None and n not in drawn:
            chain.append(n)
            n = parent[n]
        if len(drawn) + len(chain) <= node_budget:
            drawn.update(dict.fromkeys(chain))
    dead_ends = 0
    for n in sorted(dist, key=lambda n: (dist[n], n)):
        if len(drawn) >= node_budget or dead_ends >= MAX_DEAD_END_CALLERS:
            break
        if n not in drawn and dist[n] > 0 and parent[n] in drawn and graph.nodes[n].kind != "module":
            drawn[n] = None
            dead_ends += 1

    test_node_set = set(test_nodes)
    drawn_test_ids = {to_pytest_id(graph.nodes[n]) for n in drawn if n in test_node_set}

    # Selected tests not drawn as nodes become pills, grouped by file and by how they were chosen.
    groups: dict[tuple[str, bool], list[str]] = {}
    for c in selected_tests:
        if c.test_id not in drawn_test_ids:
            groups.setdefault((c.file, c.source == "graph"), []).append(c.test_id)
    pills = sorted(groups.items(), key=lambda kv: (kv[0][1] is False, kv[0][0]))

    # Radial tree layout: every leaf and every pill gets an equal slice of the circle.
    children: dict[str | None, list[str]] = {}
    for n in drawn:
        p = parent[n] if parent[n] in drawn else None
        children.setdefault(p, []).append(n)
    for kids in children.values():
        kids.sort(key=lambda n: (dist[n], graph.nodes[n].name))

    roots = children.get(None, [])
    single_root = len(roots) == 1
    top_items: list[str] = children.get(roots[0], []) if single_root else list(roots)

    leaf_memo: dict[str, int] = {}

    def leaves(n: str) -> int:
        if n not in leaf_memo:
            leaf_memo[n] = sum(leaves(k) for k in children.get(n, [])) or 1
        return leaf_memo[n]

    max_dist = max((dist[n] for n in drawn), default=0)
    pill_radius = (max(max_dist, 1) + 0.6) * RING_GAP
    total_slots = sum(leaves(n) for n in top_items) + len(pills) or 1
    slot = 2 * math.pi / total_slots

    pos: dict[str, tuple[float, float, float]] = {}  # node -> (x, y, angle)

    def radius_of(n: str) -> float:
        if single_root or dist[n] > 0:
            return dist[n] * RING_GAP
        return 0.45 * RING_GAP

    def place(n: str, start: float) -> None:
        span = leaves(n) * slot
        angle = start + span / 2
        r = radius_of(n)
        pos[n] = (r * math.cos(angle), r * math.sin(angle), angle)
        cursor = start
        for k in children.get(n, []):
            place(k, cursor)
            cursor += leaves(k) * slot

    if single_root:
        pos[roots[0]] = (0.0, 0.0, math.pi / 2)
    cursor = -math.pi / 2
    for n in top_items:
        place(n, cursor)
        cursor += leaves(n) * slot
    pill_angles = [cursor + (i + 0.5) * slot for i in range(len(pills))]

    # SVG elements
    guides, edges, nodes_svg, labels = [], [], [], []
    for d in range(1, max_dist + 1):
        r = d * RING_GAP
        guides.append(f'<circle cx="0" cy="0" r="{r}" class="ring" />')
        guides.append(f'<text x="0" y="{-r}" dy="0.35em" text-anchor="middle" class="ring-label">{d}</text>')
    if pills:
        guides.append(f'<circle cx="0" cy="0" r="{pill_radius:.0f}" class="ring ring-fallback" />')

    for n in drawn:
        p = parent[n]
        if p in pos and n in pos:
            x1, y1, _ = pos[p]
            x2, y2, _ = pos[n]
            edges.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" class="edge" />')

    if not roots:
        # Changed code not found in the graph: still mark the origin.
        changed_files = ", ".join(sorted({s.file for s in changed_symbols})) or "no changes"
        nodes_svg.append(f'<circle cx="0" cy="0" r="20" fill="{CHANGE}" class="node"><title>Your change: {html.escape(changed_files)} (not found in the code map)</title></circle>')
        labels.append(f'<text x="0" y="44" text-anchor="middle" class="label label-center">{html.escape(changed_files)}</text>')

    # Points the viewBox must contain, so the map is zoomed to its content.
    outer = pill_radius if pills else max_dist * RING_GAP
    extent: list[tuple[float, float]] = [(0, -outer - 24), (0, outer), (outer, 0), (-outer, 0), (-60, 60), (60, 60)]

    for n in drawn:
        x, y, angle = pos[n]
        node = graph.nodes[n]
        is_leaf = not children.get(n)
        failed = False
        if dist[n] == 0:
            color, role, radius = CHANGE, "Your change", 24
        elif n in test_node_set:
            test_id = to_pytest_id(node)
            failed = test_id in failed_ids
            color, role, radius = TEST, "Test that checks it", 15
        else:
            color, role, radius = CALLER, "Code that uses it", 12
        stroke = f' stroke="{CHANGE}" stroke-width="5"' if failed else ""
        steps = f"{dist[n]} step{'s' if dist[n] != 1 else ''} from your change" if dist[n] else "the code you changed"
        title = f"{role}{' (this test failed: it caught the bug)' if failed else ''}: {node.qualname} ({node.file}:{node.line}), {steps}"
        nodes_svg.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius}" fill="{color}" class="node"{stroke}>'
            f'<title>{html.escape(title)}</title></circle>'
        )
        name = html.escape(node.name)
        label_w = LABEL_CHAR_W * (len(node.name) + (17 if failed else 0))
        if failed:
            name += ' <tspan class="failed">✓ caught the bug</tspan>'
        if dist[n] == 0 and single_root:
            labels.append(f'<text x="{x:.1f}" y="{y + radius + 28:.1f}" text-anchor="middle" class="label label-center">{name}</text>')
            extent += [(x - label_w * 0.6, y + radius + 36), (x + label_w * 0.6, y + radius + 36)]
        elif is_leaf:
            labels.append(_radial_text(x, y, angle, radius + 6, name, "label"))
            reach = radius + 6 + label_w
            extent.append((x + reach * math.cos(angle), y + reach * math.sin(angle)))
        else:
            # Label on the side facing away from the centre, so it clears the centre label and inner edges.
            label_y = y + radius + 24 if math.sin(angle) > 0 else y - radius - 8
            labels.append(f'<text x="{x:.1f}" y="{label_y:.1f}" text-anchor="middle" class="label">{name}</text>')
            extent += [(x - label_w / 2, label_y - 22), (x + label_w / 2, label_y + 6)]

    for ((file, via_graph), ids), angle in zip(pills, pill_angles):
        n_failed = sum(1 for t in ids if t in failed_ids)
        text = f"{Path(file).name} · {len(ids)} more test{'s' if len(ids) != 1 else ''}"
        if n_failed:
            text += f" · ✓ {n_failed} caught the bug"
        width = PILL_CHAR_W * len(text) + 26
        flip = math.cos(angle) < -1e-9
        deg = math.degrees(angle) + (180 if flip else 0)
        rect_x = -width if flip else 0
        text_x = -width / 2 if flip else width / 2
        px, py = pill_radius * math.cos(angle), pill_radius * math.sin(angle)
        css = "pill pill-graph" if via_graph else "pill"
        if n_failed:
            css += " pill-failed"
        why = "linked to your change in the code map (too many to draw one by one)" if via_graph else "run to be safe, because this file imports the code you changed"
        title = f"{file}: {len(ids)} test(s) {why}" + "".join(f"\n{t}{' (failed: caught the bug)' if t in failed_ids else ''}" for t in ids[:30])
        if len(ids) > 30:
            title += f"\n… and {len(ids) - 30} more"
        edges.append(f'<line x1="0" y1="0" x2="{px:.1f}" y2="{py:.1f}" class="edge edge-fallback" />')
        nodes_svg.append(
            f'<g transform="translate({px:.1f},{py:.1f}) rotate({deg:.1f})"><title>{html.escape(title)}</title>'
            f'<rect x="{rect_x:.1f}" y="-19" width="{width:.1f}" height="38" rx="19" class="{css}" />'
            f'<text x="{text_x:.1f}" dy="0.35em" text-anchor="middle" class="pill-text">{html.escape(text)}</text></g>'
        )
        reach = pill_radius + width
        extent.append((reach * math.cos(angle), reach * math.sin(angle)))

    pad = 30
    min_x = min(x for x, _ in extent) - pad
    min_y = min(y for _, y in extent) - pad
    vb_w = max(x for x, _ in extent) + pad - min_x
    vb_h = max(y for _, y in extent) + pad - min_y
    svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="{min_x:.0f} {min_y:.0f} {vb_w:.0f} {vb_h:.0f}">
  <g id="guides">{"".join(guides)}</g>
  <g id="edges">{"".join(edges)}</g>
  <g id="nodes">{"".join(nodes_svg)}</g>
  <g id="labels">{"".join(labels)}</g>
</svg>"""

    # Header in plain words: what changed, how many tests ran, what happened, and the AI's read.
    changed_names = ", ".join(f"<code>{html.escape(s.qualname)}</code> in {html.escape(s.file)}" for s in changed_symbols) or "nothing"
    n_selected = report.get("selected", len(selected_tests))
    pct = f" ({100 * n_selected / total_suite_count:.1f}%)" if total_suite_count else ""
    stats = [f'<div class="stat"><span class="k">Tests RIPPLE picked</span><span class="v"><strong>{n_selected}</strong> of {total_suite_count}{pct}</span></div>']
    results = report.get("results") or {}
    if results:
        n_fail = results.get("failed", 0)
        verdict = f'<span class="v caught">✓ Bug caught</span><span class="d">{n_fail} test{"s" if n_fail != 1 else ""} failed, {results.get("passed", 0)} passed</span>' if n_fail \
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

    failed_list = ""
    if failed_ids:
        failed_list = '<div class="model"><span class="k">Caught by</span> ' + " ".join(f"<code>{html.escape(t)}</code>" for t in sorted(failed_ids)) + "</div>"

    dark = "--page: #0d0d0d; --surface: #1a1a19; --ink: #f0efec; --ink-2: #c3c2b7; --grid: #2c2c2a; --border: rgba(255,255,255,0.10); --code-bg: #262624; --pill: #262624;"
    html_page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>RIPPLE Change Map</title>
  <style>
    :root {{ color-scheme: light; --page: #f9f9f7; --surface: #fcfcfb; --ink: #0b0b0b; --ink-2: #52514e; --grid: #e1e0d9; --border: rgba(11,11,11,0.10); --code-bg: #f0efec; --pill: #ffffff; }}
    @media (prefers-color-scheme: dark) {{ :root:where(:not([data-theme="light"])) {{ color-scheme: dark; {dark} }} }}
    :root[data-theme="dark"] {{ color-scheme: dark; {dark} }}
    body {{ margin: 0; padding: 20px 24px; background: var(--page); color: var(--ink); font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }}
    h1 {{ margin: 0 0 4px; font-size: 24px; }}
    h1 span {{ color: {TEST}; }}
    .changed {{ color: var(--ink-2); font-size: 16px; margin-bottom: 14px; }}
    code {{ font-family: ui-monospace, monospace; background: var(--code-bg); padding: 1px 6px; border-radius: 4px; overflow-wrap: anywhere; }}
    .stats {{ display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 10px; }}
    .stat {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 8px 14px; display: flex; flex-direction: column; gap: 2px; }}
    .k {{ font-size: 13px; color: var(--ink-2); }}
    .v {{ font-size: 20px; }}
    .v.small {{ font-size: 15px; padding-top: 4px; }}
    .v.caught {{ color: {TEST}; font-weight: 700; }}
    .d {{ font-size: 13px; color: var(--ink-2); }}
    .model {{ font-size: 15px; margin-bottom: 8px; max-width: 1100px; line-height: 1.45; }}
    .model .k {{ margin-right: 6px; }}
    .legend {{ display: flex; flex-wrap: wrap; gap: 18px; margin: 10px 0; font-size: 14px; color: var(--ink-2); }}
    .legend span {{ display: inline-flex; align-items: center; gap: 6px; }}
    .dot {{ width: 13px; height: 13px; border-radius: 50%; display: inline-block; }}
    .chip {{ width: 24px; height: 13px; border-radius: 7px; display: inline-block; border: 1.5px dashed var(--ink-2); }}
    .container {{ border: 1px solid var(--border); border-radius: 10px; background: var(--surface); }}
    svg {{ display: block; width: 100%; height: calc(100vh - 300px); min-height: 460px; }}
    svg .ring {{ fill: none; stroke: var(--grid); stroke-width: 2; }}
    svg .ring-fallback {{ stroke: var(--ink-2); stroke-opacity: 0.5; stroke-dasharray: 8 8; }}
    svg .ring-label {{ fill: var(--ink-2); font-size: 16px; font-family: system-ui, sans-serif; paint-order: stroke; stroke: var(--surface); stroke-width: 6px; }}
    svg .edge {{ stroke: var(--ink-2); stroke-opacity: 0.6; stroke-width: 2; }}
    svg .edge-fallback {{ stroke: var(--ink-2); stroke-opacity: 0.35; stroke-width: 1.5; stroke-dasharray: 4 6; }}
    svg .node {{ stroke-linejoin: round; }}
    svg .label {{ fill: var(--ink); font-size: 22px; font-weight: 600; font-family: system-ui, sans-serif; paint-order: stroke; stroke: var(--surface); stroke-width: 6px; }}
    svg .label-center {{ font-size: 24px; }}
    svg .failed {{ fill: {TEST}; font-weight: 700; }}
    svg .pill {{ fill: var(--pill); stroke: var(--ink-2); stroke-width: 1.5; stroke-dasharray: 5 4; }}
    svg .pill-graph {{ stroke: {TEST}; stroke-dasharray: none; }}
    svg .pill-failed {{ stroke: {CHANGE}; stroke-width: 3; stroke-dasharray: none; }}
    svg .pill-text {{ fill: var(--ink); font-size: 19px; font-family: system-ui, sans-serif; }}
    .note {{ font-size: 14px; color: var(--ink-2); margin-top: 8px; max-width: 1100px; }}
  </style>
</head>
<body>
  <h1><span>RIPPLE</span> · how one change spreads to the tests</h1>
  <div class="changed">You changed {changed_names}</div>
  <div class="stats">{"".join(stats)}</div>
  {model_line}
  {failed_list}
  <div class="legend">
    <span><i class="dot" style="background:{CHANGE}"></i> Your change</span>
    <span><i class="dot" style="background:{CALLER}"></i> Code that uses it</span>
    <span><i class="dot" style="background:{TEST}"></i> Test that checks it</span>
    <span><i class="dot" style="background:{TEST};box-shadow:0 0 0 3px {CHANGE}"></i> Test that caught the bug</span>
    <span><i class="chip"></i> More tests run to be safe</span>
  </div>
  <div class="container">
    {svg_content}
  </div>
  <div class="note">Read it from the middle out. Each ring is one step further from your change: ring 1 uses your code directly, ring 2 uses something on ring 1, and so on (up to {max_depth}). The dashed outer ring holds test files RIPPLE also runs to be safe, because they import the file you changed. Hover anything for details.</div>
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
