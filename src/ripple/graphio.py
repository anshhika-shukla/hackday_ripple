"""Graphify graph loader and normalizer (see docs/graph_schema.md)."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import networkx as nx

# Relations along which a change ripples from callee to caller (src -> dst means src depends on dst).
RIPPLE_RELATIONS = {"calls", "indirect_call", "references", "uses", "inherits", "method"}
IMPORT_RELATIONS = {"imports", "imports_from", "re_exports"}


@dataclass
class Node:
    id: str
    name: str
    qualname: str
    file: str
    kind: str = "function"  # function | method | class | module | external | other
    line: int = 1
    end_line: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Edge:
    src: str
    dst: str
    relation: str
    extra: dict[str, Any] = field(default_factory=dict)


class CodeGraph:
    """Normalized code graph wrapping NetworkX DiGraph (edges point from dependent to dependency)."""

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
        return [
            pred for pred in self.g.predecessors(node_id)
            if "call" in str(self.g.edges[pred, node_id].get("relation", "")).lower()
        ]

    def find_node(self, file_path: str, qualname: str) -> str | None:
        """Find graph node ID matching a repo-relative file path and symbol qualname."""
        norm_file = normalize_path(file_path)
        short_name = qualname.split(".")[-1]

        def same_file(node: Node) -> bool:
            node_file = normalize_path(node.file)
            return bool(node_file) and (node_file == norm_file or norm_file.endswith("/" + node_file))

        in_file = [n for n in self.nodes.values() if same_file(n) and n.kind != "other"]
        # 1. Exact qualname (Class.method), 2. qualname suffix (module.Class.method), 3. short name
        for n in in_file:
            if n.qualname == qualname:
                return n.id
        for n in in_file:
            if qualname.endswith("." + n.qualname) and n.kind != "module":
                return n.id
        for n in in_file:
            if n.name == short_name and n.kind in ("function", "method", "class"):
                return n.id
        # Module-level change: qualname is the module stem
        for n in in_file:
            if n.kind == "module" and Path(n.file).stem == short_name:
                return n.id
        return None

    def module_node_for_file(self, file_path: str) -> str | None:
        norm_file = normalize_path(file_path)
        for n in self.nodes.values():
            if n.kind == "module" and normalize_path(n.file) == norm_file:
                return n.id
        return None


def normalize_path(path: str) -> str:
    p = str(path).replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p


def _parse_line(location: Any) -> int:
    """Graphify stores lines as 'L12'; older formats use ints."""
    if isinstance(location, int):
        return location
    if isinstance(location, str) and location.lstrip("L").isdigit():
        return int(location.lstrip("L"))
    return 1


def _node_kind(item: dict[str, Any], label: str, file: str) -> str:
    if item.get("external"):
        return "external"
    if item.get("_callable_class"):
        return "class"
    if item.get("_callable"):
        return "method" if label.startswith(".") else "function"
    if file and label in (Path(file).name, file, file.split("/", 1)[-1]):
        return "module"
    return item.get("kind", "other")


def load_graph(graph_path: str | Path) -> CodeGraph:
    """Load graphify-out/graph.json and normalize into CodeGraph."""
    path = Path(graph_path)
    if not path.exists():
        raise FileNotFoundError(f"Graph file not found: {path}")

    raw = json.loads(path.read_text(encoding="utf-8"))
    raw_nodes = raw.get("nodes", [])
    raw_edges = raw.get("links", raw.get("edges", []))

    # Graphify writes "directed": false, but its source/target order is reliable:
    # calls edges always go caller -> callee (verified on pallets/click, see docs/graph_schema.md).
    is_graphify = "graphify_version" in (raw.get("graph") or {})
    direction_known = True if is_graphify else bool(raw.get("directed", True))

    nodes: dict[str, Node] = {}
    for item in raw_nodes:
        nid = item.get("id")
        if not nid:
            continue
        label = str(item.get("label") or item.get("name") or nid)
        file = normalize_path(item.get("source_file") or item.get("file") or "")
        name = label.lstrip(".").removesuffix("()")
        nodes[nid] = Node(
            id=nid,
            name=name,
            qualname=item.get("qualname") or name,
            file=file,
            kind=_node_kind(item, label, file),
            line=_parse_line(item.get("source_location", item.get("line"))),
            extra=item,
        )

    edges = [
        Edge(src=e["source"], dst=e["target"], relation=str(e.get("relation", "calls")), extra=e)
        for e in raw_edges
        if e.get("source") in nodes and e.get("target") in nodes
    ]

    # Methods get Class.method qualnames from Graphify's class -method-> method edges.
    for e in edges:
        if e.relation == "method" and nodes[e.dst].qualname == nodes[e.dst].name:
            nodes[e.dst].qualname = f"{nodes[e.src].name}.{nodes[e.dst].name}"

    nx_g = nx.DiGraph()
    for nid, node in nodes.items():
        nx_g.add_node(nid, name=node.name, qualname=node.qualname, file=node.file, kind=node.kind, line=node.line)
    for e in edges:
        # DiGraph keeps one edge per pair; a direct call is the most informative relation to keep.
        if nx_g.has_edge(e.src, e.dst) and nx_g.edges[e.src, e.dst]["relation"] == "calls":
            continue
        nx_g.add_edge(e.src, e.dst, relation=e.relation)

    return CodeGraph(nx_graph=nx_g, nodes=nodes, direction_known=direction_known)
