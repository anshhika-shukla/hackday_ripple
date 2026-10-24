# Graphify `graph.json` Schema Specification

This document records the structure, conventions, and normalization rules for Graphify's `graphify-out/graph.json` based on Graphify code-only extraction (`graphify extract . --code-only`).

## 1. Top-Level Structure

A `graph.json` file produced by Graphify code-only mode contains a node-link graph representation:

```json
{
  "nodes": [
    {
      "id": "src/click/core.py::Command.invoke",
      "name": "invoke",
      "qualname": "click.core.Command.invoke",
      "file": "src/click/core.py",
      "kind": "method",
      "line": 1012,
      "end_line": 1045
    }
  ],
  "edges": [
    {
      "source": "tests/test_core.py::test_invoke_ctx",
      "target": "src/click/core.py::Command.invoke",
      "relation": "calls"
    }
  ],
  "directed": true,
  "metadata": {
    "extractor": "graphify-code",
    "version": "0.1.0"
  }
}
```

Graphify also supports dictionary-keyed node representations where `nodes` is `{ "<node_id>": { ...node_data... } }`. The RIPPLE adapter in `graphio.py` normalizes both formats into uniform dataclasses.

## 2. Node Schema

| Field | Type | Description | Fallback / Default |
|---|---|---|---|
| `id` | `str` | Unique node identifier (e.g. `path/to/file.py::QualName` or canonical path) | Required |
| `name` | `str` | Short symbol identifier (e.g. `invoke`) | Derived from `id` |
| `qualname` | `str` | Fully-qualified symbol name (e.g. `click.core.Command.invoke`) | `name` or `id` |
| `file` | `str` | Relative file path from repo root | Extracted from `id` |
| `kind` | `str` | Symbol kind: `function`, `method`, `class`, `module` | `"function"` |
| `line` | `int` | Definition starting line (1-indexed) | `start_line`, `startLine`, or `1` |
| `end_line` | `int` (opt) | Definition ending line | `endLine` or `line` |

### Test Nodes
Test nodes are recognized by:
1. `file` located inside `tests/` or named `test_*.py` or `*_test.py`.
2. `name` beginning with `test_` or belonging to a class starting with `Test`.
3. Pytest node ID mapping: `f"{file}::{qualname.replace('.', '::')}"` or `f"{file}::{name}"`.

## 3. Edge Schema & Relation Types

| Field | Type | Description |
|---|---|---|
| `source` / `src` | `str` | Source node ID |
| `target` / `dst` | `str` | Target node ID |
| `relation` / `type` | `str` | Relation type: `calls`/`call`, `imports`/`import`, `contains`, `inherits` |

> [!NOTE] Resilient Normalization
> Real Graphify extractors exhibit minor variation across releases (e.g., using `call` instead of `calls`, or `start_line` instead of `line`). RIPPLE's normalizer in `graphio.py` defensively matches substrings (`"call"` in relation) and accepts `start_line`/`startLine` fallbacks.

### Relation Semantics
- **`calls`**: `source` (caller) calls `target` (callee).
  - *Example*: `tests/test_core.py::test_command` -> `src/click/core.py::Command.invoke`.
- **`imports`**: `source` module/function imports `target` module/symbol.
  - *Example*: `src/click/core.py` -> `src/click/utils.py`.
- **`contains`**: Parent module or class defines child function or class.
  - *Example*: `src/click/core.py::Command` -> `src/click/core.py::Command.invoke`.

## 4. Directionality & Impact Traversal
- **Direction**: Edges are directed. For `calls`, the edge points from caller to callee (`A -> B` means `A` calls `B`).
- **Impact Reverse Traversal**: If function `B` changes, affected callers are found by **reversing** the `calls` relation (`incoming` edges in a directed graph, or traversing from `B` backwards to `A`).
- **Undirected Fallback**: If direction cannot be determined (`direction_known = False`), RIPPLE explores the undirected neighborhood, flagging candidates with `over_approx = True` to guarantee safety (never under-selecting tests).

## 5. Import Closure Fallback
When static call resolution misses dynamic dispatch (e.g., click's callback invocations or decorator wrapping), RIPPLE checks module-level `imports` edges:
Any test file importing the changed module is included with `source = "import_closure"`, positioned after direct call-graph candidates in the ranking.
