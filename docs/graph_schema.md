# Graphify `graph.json` schema (as observed)

Inspected from real output of `graphify extract . --code-only` (Graphify 0.9.95) on
`tests/fixtures/mini_app` and `pallets/click` 8.1.7. `src/ripple/graphio.py` normalizes it.

## Top level
NetworkX node-link format:
```json
{"directed": false, "multigraph": false,
 "graph": {"schema_version": 1, "graphify_version": "0.9.95"},
 "nodes": [...], "links": [...], "hyperedges": [...]}
```
Edges are under **`links`** (not `edges`).

## Nodes
```json
{"id": "pricing_apply_discount", "label": "apply_discount()", "source_file": "pricing.py",
 "source_location": "L4", "_callable": true, "_origin": "ast",
 "community": 3, "community_name": "Community 3", "file_type": "code", "norm_label": "apply_discount()"}
```
| What | How to recognise it |
|---|---|
| Function | `_callable: true`, label `name()` |
| Method | `_callable: true`, label `.name()`; linked from its class by a `method` edge |
| Class | `_callable_class: true`, label `Name` |
| Module (file) | label equals the file name (e.g. `pricing.py`, `click/__init__.py`), no `_callable` |
| External | `external: true`, `type: "external"`, no `source_file` (e.g. `pytest`, `os`) |
| Docstring | `*_rationale_<line>` ids, linked by `rationale_for` edges |

- File paths (`source_file`) are relative to the directory Graphify ran in (the repo root).
- Line numbers are strings like `"L4"` (start line only; no end line).
- There is **no qualname field**. RIPPLE derives `Class.method` from `method` edges.
- Ids are slug-like (`tests_test_pricing_test_apply_discount`); do not parse them.
- Functions nested inside tests (e.g. CLI callbacks named `test_*`) appear as normal function nodes; RIPPLE only treats module-level `test*` functions and `Test*` class methods as runnable tests.

## Edges (`links`)
```json
{"source": "cart_cart_get_total", "target": "pricing_apply_discount", "relation": "calls",
 "context": "call", "source_file": "cart.py", "source_location": "L24",
 "confidence": "EXTRACTED", "confidence_score": 1.0, "weight": 1.0, "_origin": "ast"}
```
Relations seen on Click (count): `contains` 985, `calls` 768, `references` 582, `method` 354,
`imports` 309, `rationale_for` 296, `indirect_call` 271, `uses` 163, `imports_from` 114,
`inherits` 41, `re_exports` 9.

| Relation | Direction (source -> target) | Used by RIPPLE for |
|---|---|---|
| `calls`, `indirect_call` | caller -> callee | ripple traversal |
| `references` | user -> referenced symbol (e.g. decorator) | ripple traversal |
| `uses` | user -> type in annotation | ripple traversal |
| `inherits` | subclass -> base | ripple traversal |
| `method` | class -> method | ripple traversal (method change reaches users of the class) |
| `imports`, `imports_from`, `re_exports` | importing file -> imported symbol/module | import-closure fallback |
| `contains` | file -> top-level symbol, function -> nested function | runnable-test detection |
| `rationale_for` | docstring -> symbol | ignored |

## Direction
The top-level flag says `"directed": false`, but source/target order is meaningful: on Click all
768 `calls` edges have `source_file` equal to the caller's file, and no test function is ever a
`calls` target. RIPPLE therefore treats Graphify graphs as directed (`direction_known = True`).

## Limits observed
- Calls through dynamic dispatch are missing (Click: `CliRunner.invoke(cli)` -> `cli.main()`).
- Attribute access on re-exported packages (`click.command`) often resolves to unnamed placeholder
  nodes without `source_file`, not to the library function.
