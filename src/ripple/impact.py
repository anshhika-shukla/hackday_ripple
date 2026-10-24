"""Graph-based change impact engine and test selection."""

from collections import deque
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from ripple.diffmap import ChangedSymbol
from ripple.graphio import CodeGraph, Node


class CandidateTest(BaseModel):
    test_id: str
    file: str
    distance: int
    direct: bool
    via: list[str] = Field(default_factory=list)
    source: str = "graph"  # graph | import_closure
    score: float = 0.0


def is_test_node(node: Node) -> bool:
    """Determine if a graph node represents a pytest test."""
    norm_file = node.file.replace("\\", "/").lower()
    in_test_dir = "/test" in norm_file or norm_file.startswith("test")
    is_test_func = node.name.startswith("test_") or "Test" in node.qualname
    return in_test_dir and is_test_func


def to_pytest_id(node: Node) -> str:
    """Format node into a standard pytest node ID."""
    norm_file = node.file.replace("\\", "/").lstrip("./")
    if "::" in node.id and node.id.startswith(norm_file):
        return node.id
    short_sym = node.name
    if "Test" in node.qualname and "." in node.qualname:
        parts = node.qualname.split(".")
        short_sym = "::".join(parts[-2:])
    return f"{norm_file}::{short_sym}"


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
        changed_files.add(sym.file.replace("\\", "/").lstrip("./"))
        nid = sym.node_id or graph.find_node(sym.file, sym.qualname)
        if nid and nid in graph.nodes:
            start_nodes.append(nid)

    if not start_nodes:
        # Fallback: if no symbols resolved directly, try matching files
        for nid, node in graph.nodes.items():
            nfile = node.file.replace("\\", "/").lstrip("./")
            if any(nfile == cf or nfile.endswith(cf) for cf in changed_files):
                start_nodes.append(nid)

    if not start_nodes:
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

        curr_node = graph.get_node(curr_id)

        # Get callers: in directed graph caller -> callee, incoming predecessors are callers
        if graph.direction_known:
            neighbors = list(graph.g.predecessors(curr_id))
        else:
            # Undirected neighborhood
            neighbors = list(graph.g.neighbors(curr_id))

        for nbr_id in neighbors:
            edge_data = graph.g.get_edge_data(nbr_id, curr_id) or graph.g.get_edge_data(curr_id, nbr_id) or {}
            rel = str(edge_data.get("relation", "calls")).lower()
            if not any(k in rel for k in ("call", "contain", "import")):
                continue

            nbr_dist = dist + 1
            nbr_node = graph.get_node(nbr_id)
            nbr_name = nbr_node.name if nbr_node else nbr_id
            new_path = path + [nbr_name]

            if nbr_id not in visited_distances or nbr_dist < visited_distances[nbr_id]:
                visited_distances[nbr_id] = nbr_dist
                best_paths[nbr_id] = new_path
                queue.append((nbr_id, nbr_dist, new_path))

                if nbr_node and is_test_node(nbr_node):
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

    # 3. Import-closure fallback
    if include_import_closure:
        # Check test nodes whose file imports any changed module
        for nid, node in graph.nodes.items():
            if is_test_node(node):
                pytest_id = to_pytest_id(node)
                if pytest_id in candidates_map:
                    continue

                test_file = node.file.replace("\\", "/").lstrip("./")
                # Look for import edge from test_file to changed module
                imports_changed = False
                for cf in changed_files:
                    cf_stem = Path(cf).stem
                    # check edges in graph
                    for u, v, data in graph.g.edges(data=True):
                        if "import" in str(data.get("relation", "")).lower():
                            u_norm = str(u).replace("\\", "/").lstrip("./")
                            v_norm = str(v).replace("\\", "/").lstrip("./")
                            if (u_norm == test_file or test_file in u_norm) and (cf_stem in v_norm or cf in v_norm):
                                imports_changed = True
                                break
                    if imports_changed:
                        break

                if imports_changed:
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
