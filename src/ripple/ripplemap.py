"""Standalone offline HTML/SVG ripple map generator."""

import argparse
import html
import re
from pathlib import Path
from typing import Any

import networkx as nx

from ripple.diffmap import ChangedSymbol, parse_diff
from ripple.graphio import CodeGraph, load_graph
from ripple.impact import CandidateTest, compute_impact


def build_ripple_map_html(
    graph: CodeGraph,
    changed_symbols: list[ChangedSymbol],
    selected_tests: list[CandidateTest],
    total_suite_count: int,
    max_nodes: int = 120,
) -> str:
    """Generate standalone offline HTML with inline SVG visualizing change impact."""
    # Classify nodes:
    # Red: Changed symbols
    # Green: Selected tests
    # Amber: Impacted intermediate functions/methods
    # Grey: Other context nodes

    changed_node_ids = set()
    for s in changed_symbols:
        nid = s.node_id or graph.find_node(s.file, s.qualname)
        if nid and nid in graph.nodes:
            changed_node_ids.add(nid)

    selected_test_ids = {c.test_id for c in selected_tests}
    selected_test_nodes = set()
    for nid, node in graph.nodes.items():
        from ripple.impact import to_pytest_id
        if to_pytest_id(node) in selected_test_ids:
            selected_test_nodes.add(nid)

    # Subgraph extraction around changed nodes
    nodes_to_include = set(changed_node_ids | selected_test_nodes)
    for c in selected_tests:
        for step in c.via:
            for nid, node in graph.nodes.items():
                if node.name == step or node.qualname == step:
                    nodes_to_include.add(nid)

    # If too few, add 1-hop neighbors
    for cn in list(changed_node_ids):
        if graph.g.has_node(cn):
            nodes_to_include.update(graph.g.predecessors(cn))
            nodes_to_include.update(graph.g.successors(cn))

    if not nodes_to_include:
        # Fallback to first few graph nodes
        nodes_to_include = set(list(graph.nodes.keys())[:20])

    sub_nodes = list(nodes_to_include)[:max_nodes]
    subgraph = graph.g.subgraph(sub_nodes).to_undirected()

    # Layout with deterministic seed
    pos = nx.spring_layout(subgraph, seed=7, k=1.2)

    width = 1000
    height = 700
    padding = 80

    # Scale coordinates to SVG viewport
    xs = [coord[0] for coord in pos.values()] or [0]
    ys = [coord[1] for coord in pos.values()] or [0]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = (max_x - min_x) if max_x != min_x else 1.0
    span_y = (max_y - min_y) if max_y != min_y else 1.0

    def to_svg_coord(x, y):
        cx = padding + ((x - min_x) / span_x) * (width - 2 * padding)
        cy = padding + ((y - min_y) / span_y) * (height - 2 * padding)
        return cx, cy

    # Generate SVG Elements
    edges_svg = []
    for u, v in subgraph.edges():
        if u in pos and v in pos:
            x1, y1 = to_svg_coord(*pos[u])
            x2, y2 = to_svg_coord(*pos[v])
            edges_svg.append(
                f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#374151" stroke-width="1.5" stroke-opacity="0.6" />'
            )

    nodes_svg = []
    labels_svg = []

    for nid in sub_nodes:
        x, y = to_svg_coord(*pos[nid])
        node_obj = graph.get_node(nid)
        name = node_obj.name if node_obj else nid
        qualname = node_obj.qualname if node_obj else name

        if nid in changed_node_ids:
            color = "#ef4444"  # Red
            role = "Changed Symbol"
            radius = 14
        elif nid in selected_test_nodes:
            color = "#10b981"  # Green
            role = "Selected Test"
            radius = 12
        else:
            color = "#f59e0b"  # Amber (impacted caller / via)
            role = "Impacted Node"
            radius = 9

        escaped_name = html.escape(name)
        escaped_title = html.escape(f"{role}: {qualname} ({nid})")

        nodes_svg.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius}" fill="{color}" stroke="#111827" stroke-width="2">\n'
            f'  <title>{escaped_title}</title>\n'
            f'</circle>'
        )

        # Draw labels for top nodes (changed, tests, or prominent)
        if radius >= 12 or len(sub_nodes) <= 15:
            labels_svg.append(
                f'<text x="{x:.1f}" y="{(y - radius - 4):.1f}" font-family="system-ui, sans-serif" font-size="11" font-weight="600" fill="#f3f4f6" text-anchor="middle">{escaped_name}</text>'
            )

    svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="100%" style="background-color: #111827; border-radius: 8px;">
  <!-- Edges -->
  <g id="edges">
    {"".join(edges_svg)}
  </g>
  <!-- Nodes -->
  <g id="nodes">
    {"".join(nodes_svg)}
  </g>
  <!-- Labels -->
  <g id="labels">
    {"".join(labels_svg)}
  </g>
</svg>"""

    html_page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>RIPPLE Impact Map</title>
  <style>
    body {{
      margin: 0;
      padding: 24px;
      background: #0f172a;
      color: #f8fafc;
      font-family: system-ui, -apple-system, sans-serif;
    }}
    .header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
    }}
    h1 {{
      margin: 0;
      font-size: 24px;
      font-weight: 700;
      color: #38bdf8;
    }}
    .stat-badge {{
      font-size: 16px;
      font-weight: 600;
      background: #1e293b;
      padding: 8px 16px;
      border-radius: 6px;
      border: 1px solid #334155;
    }}
    .legend {{
      display: flex;
      gap: 16px;
      margin-bottom: 16px;
      font-size: 13px;
    }}
    .legend-item {{
      display: flex;
      align-items: center;
      gap: 6px;
    }}
    .dot {{
      width: 12px;
      height: 12px;
      border-radius: 50%;
      display: inline-block;
    }}
    .container {{
      border: 1px solid #334155;
      border-radius: 8px;
      overflow: hidden;
      box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.5);
    }}
  </style>
</head>
<body>
  <div class="header">
    <h1>🌊 RIPPLE Code Ripple Map</h1>
    <div class="stat-badge">
      <strong>{len(selected_tests)}</strong> of <strong>{total_suite_count}</strong> tests selected
    </div>
  </div>

  <div class="legend">
    <div class="legend-item"><span class="dot" style="background:#ef4444"></span> Changed Symbol (Origin)</div>
    <div class="legend-item"><span class="dot" style="background:#f59e0b"></span> Impacted Function / Method</div>
    <div class="legend-item"><span class="dot" style="background:#10b981"></span> Selected Test Case</div>
  </div>

  <div class="container">
    {svg_content}
  </div>
</body>
</html>
"""
    return html_page


def generate_map_cli(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    from ripple.cli import find_graph_file, get_diff_text
    diff_text = get_diff_text(repo)
    changed_symbols = parse_diff(repo=repo, patch_text=diff_text if diff_text else None)

    graph_path = find_graph_file(repo, args.graph)
    if not graph_path:
        print("Error: graph.json not found.", file=sys.stderr)
        return 2

    graph = load_graph(graph_path)
    candidates, _ = compute_impact(graph, changed_symbols)
    html_content = build_ripple_map_html(
        graph=graph,
        changed_symbols=changed_symbols,
        selected_tests=candidates,
        total_suite_count=len(graph.nodes),
    )

    out_file = Path(args.out)
    out_file.write_text(html_content, encoding="utf-8")
    print(f"✅ RIPPLE map written to {out_file.resolve()}")
    return 0
