"""Map git diff hunks to changed Python symbols and AST structures."""

import argparse
import ast
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, Field


class ChangedSymbol(BaseModel):
    file: str
    qualname: str
    kind: str  # function | method | class | module | added | deleted
    changed_lines: list[int] = Field(default_factory=list)
    ast_equal: bool = False
    old_src: str | None = None
    new_src: str | None = None
    node_id: str | None = None


def _strip_docstring(node: ast.AST) -> None:
    """Remove docstring expressions from function, class, or module AST nodes."""
    for n in ast.walk(node):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
            if (
                n.body
                and isinstance(n.body[0], ast.Expr)
                and isinstance(n.body[0].value, (ast.Constant, getattr(ast, "Str", type(None))))
            ):
                n.body = n.body[1:]


def _normalize_ast_for_comparison(node: ast.AST) -> str:
    """Normalize AST by stripping docstrings, line numbers, and formatting."""
    copied = ast.fix_missing_locations(node)
    _strip_docstring(copied)
    for n in ast.walk(copied):
        for attr in ("lineno", "col_offset", "end_lineno", "end_col_offset"):
            if hasattr(n, attr):
                try:
                    delattr(n, attr)
                except Exception:
                    pass
    return ast.dump(copied)


class ASTSymbolCollector(ast.NodeVisitor):
    """Collects symbols with their qualified names, scopes, and line ranges."""

    def __init__(self, filename: str):
        self.filename = filename
        self.symbols: list[dict[str, Any]] = []
        self._scope: list[str] = []

    def visit_ClassDef(self, node: ast.ClassDef):
        qualname = ".".join(self._scope + [node.name])
        self.symbols.append(
            {
                "name": node.name,
                "qualname": qualname,
                "kind": "class",
                "start_line": getattr(node, "lineno", 1),
                "end_line": getattr(node, "end_lineno", getattr(node, "lineno", 1)),
                "node": node,
            }
        )
        self._scope.append(node.name)
        self.generic_visit(node)
        self._scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._record_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._record_function(node)

    def _record_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef):
        kind = "method" if self._scope else "function"
        qualname = ".".join(self._scope + [node.name])
        self.symbols.append(
            {
                "name": node.name,
                "qualname": qualname,
                "kind": kind,
                "start_line": getattr(node, "lineno", 1),
                "end_line": getattr(node, "end_lineno", getattr(node, "lineno", 1)),
                "node": node,
            }
        )
        self._scope.append(node.name)
        self.generic_visit(node)
        self._scope.pop()


def _get_symbols_from_source(source: str, filename: str) -> list[dict[str, Any]]:
    if not source.strip():
        return []
    try:
        tree = ast.parse(source, filename=filename)
        collector = ASTSymbolCollector(filename)
        collector.visit(tree)
        return collector.symbols
    except SyntaxError:
        return []


def _find_enclosing_symbol(line_number: int, symbols: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Find the innermost enclosing symbol (function/method/class) for a line."""
    candidates = [
        s for s in symbols if s["start_line"] <= line_number <= s["end_line"]
    ]
    if not candidates:
        return None
    # Innermost = smallest span
    candidates.sort(key=lambda s: (s["end_line"] - s["start_line"]))
    return candidates[0]


def _get_git_file_content(repo_path: Path, ref: str, relative_path: str) -> str:
    """Retrieve file contents from a specific git ref using git show."""
    try:
        cmd = ["git", "-C", str(repo_path), "show", f"{ref}:{relative_path}"]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return proc.stdout
    except Exception:
        return ""


def parse_diff(
    repo: str | Path,
    base: str = "HEAD",
    patch_text: str | None = None,
    find_node_fn: Callable[[str, str], str | None] | None = None,
) -> list[ChangedSymbol]:
    """Parse git diff and map modified lines to changed Python symbols."""
    repo_path = Path(repo).resolve()

    if patch_text is None:
        try:
            cmd = ["git", "-C", str(repo_path), "diff", "-U0", base]
            proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
            diff_output = proc.stdout
        except Exception:
            return []
    else:
        diff_output = patch_text

    if not diff_output.strip():
        return []

    # Parse git diff per file
    file_diffs = re.split(r"(?=diff --git )", diff_output)
    changed_symbols: list[ChangedSymbol] = []
    seen_keys: set[tuple[str, str]] = set()

    for file_diff in file_diffs:
        if not file_diff.strip():
            continue

        match = re.search(r"diff --git a/(.*?) b/(.*)", file_diff.splitlines()[0])
        if not match:
            continue
        old_path_str = match.group(1)
        new_path_str = match.group(2)

        # Skip non-Python files
        if not (old_path_str.endswith(".py") or new_path_str.endswith(".py")):
            continue

        is_deleted = "/dev/null" in file_diff or "deleted file mode" in file_diff
        is_new = "/dev/null" in file_diff or "new file mode" in file_diff

        target_file = old_path_str if is_deleted else new_path_str

        # Get old and new source code
        if is_new:
            old_source = ""
            new_file_path = repo_path / target_file
            new_source = new_file_path.read_text(encoding="utf-8", errors="replace") if new_file_path.exists() else ""
        elif is_deleted:
            old_source = _get_git_file_content(repo_path, base, target_file)
            new_source = ""
        else:
            old_source = _get_git_file_content(repo_path, base, target_file)
            new_file_path = repo_path / target_file
            new_source = new_file_path.read_text(encoding="utf-8", errors="replace") if new_file_path.exists() else ""

        old_symbols = _get_symbols_from_source(old_source, target_file)
        new_symbols = _get_symbols_from_source(new_source, target_file)

        # Parse hunks
        # @@ -old_start,old_count +new_start,new_count @@
        hunk_headers = re.finditer(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", file_diff)
        changed_lines_new: list[int] = []
        changed_lines_old: list[int] = []

        for h in hunk_headers:
            old_start = int(h.group(1))
            old_count = int(h.group(2)) if h.group(2) is not None else 1
            new_start = int(h.group(3))
            new_count = int(h.group(4)) if h.group(4) is not None else 1

            if new_count == 0:
                # pure deletion
                changed_lines_old.extend(range(old_start, old_start + max(old_count, 1)))
            else:
                changed_lines_new.extend(range(new_start, new_start + new_count))
                if old_count > 0:
                    changed_lines_old.extend(range(old_start, old_start + old_count))

        if is_deleted:
            for s in old_symbols:
                key = (target_file, s["qualname"])
                if key not in seen_keys:
                    seen_keys.add(key)
                    node_id = find_node_fn(target_file, s["qualname"]) if find_node_fn else None
                    changed_symbols.append(
                        ChangedSymbol(
                            file=target_file,
                            qualname=s["qualname"],
                            kind="deleted",
                            changed_lines=changed_lines_old,
                            ast_equal=False,
                            old_src=ast.unparse(s["node"]) if hasattr(ast, "unparse") else "",
                            new_src=None,
                            node_id=node_id,
                        )
                    )
            continue

        if is_new:
            for s in new_symbols:
                key = (target_file, s["qualname"])
                if key not in seen_keys:
                    seen_keys.add(key)
                    node_id = find_node_fn(target_file, s["qualname"]) if find_node_fn else None
                    changed_symbols.append(
                        ChangedSymbol(
                            file=target_file,
                            qualname=s["qualname"],
                            kind="added",
                            changed_lines=changed_lines_new,
                            ast_equal=False,
                            old_src=None,
                            new_src=ast.unparse(s["node"]) if hasattr(ast, "unparse") else "",
                            node_id=node_id,
                        )
                    )
            continue

        # Check for added/deleted functions between old and new
        old_map = {s["qualname"]: s for s in old_symbols}
        new_map = {s["qualname"]: s for s in new_symbols}

        for qname, s in new_map.items():
            if qname not in old_map:
                key = (target_file, qname)
                if key not in seen_keys:
                    seen_keys.add(key)
                    node_id = find_node_fn(target_file, qname) if find_node_fn else None
                    changed_symbols.append(
                        ChangedSymbol(
                            file=target_file,
                            qualname=qname,
                            kind="added",
                            changed_lines=list(range(s["start_line"], s["end_line"] + 1)),
                            ast_equal=False,
                            old_src=None,
                            new_src=ast.unparse(s["node"]) if hasattr(ast, "unparse") else "",
                            node_id=node_id,
                        )
                    )

        for qname, s in old_map.items():
            if qname not in new_map:
                key = (target_file, qname)
                if key not in seen_keys:
                    seen_keys.add(key)
                    node_id = find_node_fn(target_file, qname) if find_node_fn else None
                    changed_symbols.append(
                        ChangedSymbol(
                            file=target_file,
                            qualname=qname,
                            kind="deleted",
                            changed_lines=list(range(s["start_line"], s["end_line"] + 1)),
                            ast_equal=False,
                            old_src=ast.unparse(s["node"]) if hasattr(ast, "unparse") else "",
                            new_src=None,
                            node_id=node_id,
                        )
                    )

        # Process modified lines in new source
        lines_to_check = changed_lines_new if changed_lines_new else changed_lines_old
        module_level_lines: list[int] = []

        # Map each line to enclosing symbol
        lines_by_symbol: dict[str, list[int]] = {}
        for line in lines_to_check:
            sym = _find_enclosing_symbol(line, new_symbols if changed_lines_new else old_symbols)
            if sym:
                lines_by_symbol.setdefault(sym["qualname"], []).append(line)
            else:
                module_level_lines.append(line)

        for qname, lines in lines_by_symbol.items():
            key = (target_file, qname)
            if key in seen_keys:
                continue
            seen_keys.add(key)

            s_new = new_map.get(qname)
            s_old = old_map.get(qname)
            ast_eq = False
            old_src_str = None
            new_src_str = None

            if s_new and s_old:
                try:
                    norm_old = _normalize_ast_for_comparison(s_old["node"])
                    norm_new = _normalize_ast_for_comparison(s_new["node"])
                    ast_eq = norm_old == norm_new
                except Exception:
                    ast_eq = False

                if hasattr(ast, "unparse"):
                    try:
                        old_src_str = ast.unparse(s_old["node"])
                        new_src_str = ast.unparse(s_new["node"])
                    except Exception:
                        pass

            node_id = find_node_fn(target_file, qname) if find_node_fn else None
            kind = s_new["kind"] if s_new else (s_old["kind"] if s_old else "function")

            changed_symbols.append(
                ChangedSymbol(
                    file=target_file,
                    qualname=qname,
                    kind=kind,
                    changed_lines=lines,
                    ast_equal=ast_eq,
                    old_src=old_src_str,
                    new_src=new_src_str,
                    node_id=node_id,
                )
            )

        # Module-level changes
        if module_level_lines:
            mod_qualname = Path(target_file).stem
            key = (target_file, mod_qualname)
            if key not in seen_keys:
                seen_keys.add(key)
                ast_eq = False
                if old_source and new_source:
                    try:
                        old_tree = ast.parse(old_source, filename=target_file)
                        new_tree = ast.parse(new_source, filename=target_file)
                        ast_eq = _normalize_ast_for_comparison(old_tree) == _normalize_ast_for_comparison(new_tree)
                    except Exception:
                        ast_eq = False

                node_id = find_node_fn(target_file, mod_qualname) if find_node_fn else None
                changed_symbols.append(
                    ChangedSymbol(
                        file=target_file,
                        qualname=mod_qualname,
                        kind="module",
                        changed_lines=module_level_lines,
                        ast_equal=ast_eq,
                        old_src=old_source[:500] if old_source else None,
                        new_src=new_source[:500] if new_source else None,
                        node_id=node_id,
                    )
                )

    return changed_symbols


def main():
    parser = argparse.ArgumentParser(description="Map git diff to changed Python symbols.")
    parser.add_argument("--repo", default=".", help="Repository root path")
    parser.add_argument("--base", default="HEAD", help="Git diff base reference")
    args = parser.parse_args()

    symbols = parse_diff(repo=args.repo, base=args.base)
    for sym in symbols:
        print(f"{sym.file}::{sym.qualname} ({sym.kind}) ast_equal={sym.ast_equal} lines={sym.changed_lines}")


if __name__ == "__main__":
    main()
