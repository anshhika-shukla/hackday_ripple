"""Graphify graph loader and normalizer."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import networkx as nx


@dataclass
class Node:
    id: str
    name: str
    qualname: str
    file: str
    kind: str = "function"
    line: int = 1
    end_line: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Edge:
    src: str
    dst: str
    relation: str  # calls | imports | contains | inherits
    extra: dict[str, Any] = field(default_factory=dict)


class CodeGraph:
    """Normalized code graph wrapping NetworkX DiGraph."""

    def __init__(self, nx_graph: nx.DiGraph, nodes: dict[str, Node], direction_known: bool = True):
        self.g = nx_graph
        self.nodes = nodes
        self.direction_known = direction_known

    def get_node(self, node_id: str) -> Node | None:
        return self.nodes.get(node_id)

    def callers_of(self, node_id: str) -> list[str]:
        """Return immediate callers (source nodes having a 'calls' edge to node_id)."""
        if not self.g.has_node(node_id):
            return []
        callers = []
        # Predecessors in caller -> callee directed graph
        for pred in self.g.predecessors(node_id):
            edge_data = self.g.get_edge_data(pred, node_id, default={})
            rel = str(edge_data.get("relation", "")).lower()
            if "call" in rel:
                callers.append(pred)
        return callers

    def find_node(self, file_path: str, qualname: str) -> str | None:
        """Find graph node ID matching a relative file path and symbol qualname."""
        norm_file = file_path.replace("\\", "/").lstrip("./")
        short_name = qualname.split(".")[-1]

        # 1. Exact id or qualname match
        for nid, node in self.nodes.items():
            node_file = node.file.replace("\\", "/").lstrip("./")
            if (node_file == norm_file or node_file.endswith(norm_file) or norm_file.endswith(node_file)):
                if node.qualname == qualname or node.name == qualname or node.name == short_name:
                    return nid

        # 2. Relaxed match by qualname or short name
        for nid, node in self.nodes.items():
            if node.qualname == qualname or node.name == qualname or node.name == short_name:
                return nid

        return None


def load_graph(graph_path: str | Path) -> CodeGraph:
    """Load graphify-out/graph.json and normalize into CodeGraph."""
    path = Path(graph_path)
    if not path.exists():
        raise FileNotFoundError(f"Graph file not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    nodes: dict[str, Node] = {}
    edges: list[Edge] = []
    direction_known = True

    if isinstance(raw, dict):
        direction_known = raw.get("directed", True)
        raw_nodes = raw.get("nodes", [])
        raw_edges = raw.get("edges", raw.get("links", []))

        # Handle nodes list or dict
        if isinstance(raw_nodes, list):
            for item in raw_nodes:
                nid = item.get("id") or item.get("name")
                if not nid:
                    continue
                name = item.get("name") or str(nid).split("::")[-1]
                qualname = item.get("qualname") or name
                file = item.get("file") or (str(nid).split("::")[0] if "::" in str(nid) else "")
                kind = item.get("kind", "function")
                line = item.get("line") or item.get("start_line") or item.get("startLine", 1)
                end_line = item.get("end_line") or item.get("endLine")
                nodes[nid] = Node(
                    id=nid,
                    name=name,
                    qualname=qualname,
                    file=file,
                    kind=kind,
                    line=line,
                    end_line=end_line,
                    extra=item,
                )
        elif isinstance(raw_nodes, dict):
            for nid, item in raw_nodes.items():
                name = item.get("name") or str(nid).split("::")[-1]
                qualname = item.get("qualname") or name
                file = item.get("file") or (str(nid).split("::")[0] if "::" in str(nid) else "")
                line = item.get("line") or item.get("start_line") or item.get("startLine", 1)
                end_line = item.get("end_line") or item.get("endLine")
                nodes[nid] = Node(
                    id=nid,
                    name=name,
                    qualname=qualname,
                    file=file,
                    kind=item.get("kind", "function"),
                    line=line,
                    end_line=end_line,
                    extra=item,
                )

        # Handle edges
        if isinstance(raw_edges, list):
            for item in raw_edges:
                src = item.get("source") or item.get("src")
                dst = item.get("target") or item.get("dst")
                rel = item.get("relation") or item.get("type", "calls")
                if src and dst:
                    edges.append(Edge(src=src, dst=dst, relation=rel, extra=item))

    nx_g = nx.DiGraph()
    for nid, node in nodes.items():
        nx_g.add_node(nid, **node.__dict__)

    for edge in edges:
        nx_g.add_edge(edge.src, edge.dst, relation=edge.relation, **edge.extra)

    return CodeGraph(nx_graph=nx_g, nodes=nodes, direction_known=direction_known)
