"""Graph-based change impact engine and test selection."""

from collections import deque
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from ripple.diffmap import ChangedSymbol
from ripple.graphio import IMPORT_RELATIONS, RIPPLE_RELATIONS, CodeGraph, Node, normalize_path


class CandidateTest(BaseModel):
    test_id: str
    file: str
    distance: int
    direct: bool
    via: list[str] = Field(default_factory=list)
    source: str = "graph"  # graph | import_closure
    score: float = 0.0


def is_test_file(path: str) -> bool:
    norm_file = normalize_path(path).lower()
    name = norm_file.rsplit("/", 1)[-1]
    return norm_file.startswith("test") or "/test" in norm_file or name.startswith("test_") or name.endswith("_test.py")


def is_test_node(node: Node) -> bool:
    """Determine if a graph node represents a pytest test function or method."""
    return node.kind in ("function", "method") and node.name.startswith("test") and is_test_file(node.file)


def is_runnable_test(graph: CodeGraph, node: Node) -> bool:
    """A test pytest can address: a module-level test function or a method of a Test* class.

    Functions nested inside tests (e.g. CLI callbacks named test_*) look like tests but are not collected.
    """
    if not is_test_node(node):
        return False
    for p in graph.g.predecessors(node.id):
        rel, parent = graph.g.edges[p, node.id].get("relation"), graph.nodes[p]
        if rel == "contains" and parent.kind == "module":
            return True
        if rel == "method" and parent.kind == "class" and parent.name.startswith("Test"):
            return True
    return False


def to_pytest_id(node: Node) -> str:
    """Format node into a pytest node ID: file::func or file::TestClass::method."""
    return f"{normalize_path(node.file)}::{node.qualname.replace('.', '::')}"


def _ripple_neighbors(graph: CodeGraph, node_id: str) -> list[str]:
    """Nodes that depend on node_id (callers, users, subclasses, owning class)."""
    if graph.direction_known:
        pairs = [(p, node_id) for p in graph.g.predecessors(node_id)]
    else:
        pairs = [(p, node_id) for p in graph.g.predecessors(node_id)] + [(node_id, s) for s in graph.g.successors(node_id)]
    out = []
    for u, v in pairs:
        if graph.g.edges[u, v].get("relation") in RIPPLE_RELATIONS:
            out.append(u if v == node_id else v)
    return out


def files_importing(graph: CodeGraph, changed_files: set[str]) -> set[str]:
    """Files that transitively import any changed file (file-level import closure)."""
    importers: dict[str, set[str]] = {}
    for u, v, data in graph.g.edges(data=True):
        if data.get("relation") not in IMPORT_RELATIONS:
            continue
        src, dst = graph.nodes[u], graph.nodes[v]
        if src.kind == "module" and dst.file and dst.file != src.file:
            importers.setdefault(dst.file, set()).add(src.file)

    seen: set[str] = set()
    frontier = [f for f in changed_files]
    while frontier:
        f = frontier.pop()
        for imp in importers.get(f, ()):
            if imp not in seen and imp not in changed_files:
                seen.add(imp)
                frontier.append(imp)
    return seen


def compute_impact(
    graph: CodeGraph,
    changed_symbols: list[ChangedSymbol],
    max_depth: int = 3,
    include_import_closure: bool = True,
) -> tuple[list[CandidateTest], bool]:
    """
    Reverse BFS traversal along call relations to discover candidate tests.
    Returns (candidate_tests, over_approx_flag).
    """
    over_approx = not graph.direction_known

    # 1. Map changed symbols to graph nodes
    start_nodes: list[str] = []
    changed_files: set[str] = set()

    for sym in changed_symbols:
        nid = sym.node_id or graph.find_node(sym.file, sym.qualname)
        if nid and nid in graph.nodes:
            start_nodes.append(nid)
            changed_files.add(graph.nodes[nid].file)
        else:
            # Unresolved symbol (e.g. module-level code): start from every symbol defined in its file.
            norm = normalize_path(sym.file)
            for node in graph.nodes.values():
                if node.file and (norm == node.file or norm.endswith("/" + node.file)):
                    changed_files.add(node.file)
                    if node.kind in ("function", "method", "class"):
                        start_nodes.append(node.id)

    if not start_nodes and not changed_files:
        return [], over_approx

    # 2. BFS Traversal
    # queue: (current_node, distance, path_via)
    queue: deque[tuple[str, int, list[str]]] = deque()
    visited_distances: dict[str, int] = {}
    best_paths: dict[str, list[str]] = {}

    for sn in start_nodes:
        sym_node = graph.get_node(sn)
        name = sym_node.name if sym_node else sn
        queue.append((sn, 0, [name]))
        visited_distances[sn] = 0
        best_paths[sn] = [name]

    candidates_map: dict[str, CandidateTest] = {}

    while queue:
        curr_id, dist, path = queue.popleft()

        if dist >= max_depth:
            continue

        for nbr_id in _ripple_neighbors(graph, curr_id):
            nbr_dist = dist + 1
            nbr_node = graph.get_node(nbr_id)
            nbr_name = nbr_node.name if nbr_node else nbr_id
            new_path = path + [nbr_name]

            if nbr_id not in visited_distances or nbr_dist < visited_distances[nbr_id]:
                visited_distances[nbr_id] = nbr_dist
                best_paths[nbr_id] = new_path
                queue.append((nbr_id, nbr_dist, new_path))

                if nbr_node and is_runnable_test(graph, nbr_node):
                    pytest_id = to_pytest_id(nbr_node)
                    is_direct = (nbr_dist == 1)
                    score = 1.0 / (1.0 + nbr_dist) + (0.5 if is_direct else 0.0)

                    if pytest_id not in candidates_map or candidates_map[pytest_id].distance > nbr_dist:
                        candidates_map[pytest_id] = CandidateTest(
                            test_id=pytest_id,
                            file=nbr_node.file,
                            distance=nbr_dist,
                            direct=is_direct,
                            via=new_path,
                            source="graph",
                            score=score,
                        )

    # 3. Import-closure fallback: tests in files that (transitively) import a changed file
    if include_import_closure:
        importing = files_importing(graph, changed_files)
        for node in graph.nodes.values():
            if is_runnable_test(graph, node) and (node.file in importing or node.file in changed_files):
                pytest_id = to_pytest_id(node)
                if pytest_id not in candidates_map:
                    candidates_map[pytest_id] = CandidateTest(
                        test_id=pytest_id,
                        file=node.file,
                        distance=max_depth + 1,
                        direct=False,
                        via=["import_closure"],
                        source="import_closure",
                        score=0.1,
                    )

    # Convert to list and sort by baseline ranking B
    candidates = list(candidates_map.values())
    candidates.sort(key=lambda c: (-c.score, c.distance, c.test_id))
    return candidates, over_approx


def baseline_ranking_a(candidates: list[CandidateTest], changed_symbols: list[ChangedSymbol]) -> list[CandidateTest]:
    """Baseline Ranking A: File-name heuristic (tests/test_<module>.py first)."""
    changed_stems = {Path(s.file).stem for s in changed_symbols}

    def score_a(c: CandidateTest) -> tuple[int, int]:
        c_file_stem = Path(c.file).stem
        matches = any(c_file_stem == f"test_{stem}" or c_file_stem == f"{stem}_test" for stem in changed_stems)
        # Matches come first (0), then non-matches (1), then distance
        return (0 if matches else 1, c.distance)

    return sorted(candidates, key=score_a)


def baseline_ranking_b(candidates: list[CandidateTest]) -> list[CandidateTest]:
    """Baseline Ranking B: 1/(1+distance), +bonus if direct call."""
    return sorted(candidates, key=lambda c: (-c.score, c.distance, c.test_id))
