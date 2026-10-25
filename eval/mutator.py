"""AST-based deterministic mutation testing engine for Python codebases."""

import ast
import copy
import difflib
import random
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Mutant:
    mutant_id: int
    file: str
    line: int
    operator: str
    original_code: str
    mutated_code: str
    diff: str


class ASTMutator(ast.NodeTransformer):
    """Transformer that applies a specific mutation operator at a designated line."""

    def __init__(self, target_line: int, operator: str):
        self.target_line = target_line
        self.operator = operator
        self.applied = False
        # Source span of the replaced expression and its new text, so only that span is rewritten.
        self.span: tuple[int, int, int, int] | None = None
        self.replacement: str | None = None

    def _record(self, original: ast.AST, mutated: ast.AST) -> None:
        self.span = (original.lineno, original.col_offset, original.end_lineno, original.end_col_offset)
        self.replacement = ast.unparse(mutated)
        self.applied = True

    def visit_Compare(self, node: ast.Compare):
        if self.applied or getattr(node, "lineno", -1) != self.target_line:
            return self.generic_visit(node)

        if self.operator == "CMP_FLIP" and node.ops:
            op = node.ops[0]
            new_op = None
            if isinstance(op, ast.Lt):
                new_op = ast.LtE()
            elif isinstance(op, ast.LtE):
                new_op = ast.Lt()
            elif isinstance(op, ast.Gt):
                new_op = ast.GtE()
            elif isinstance(op, ast.GtE):
                new_op = ast.Gt()
            elif isinstance(op, ast.Eq):
                new_op = ast.NotEq()
            elif isinstance(op, ast.NotEq):
                new_op = ast.Eq()

            if new_op:
                original = copy.deepcopy(node)
                node.ops[0] = new_op
                self._record(original, node)
                return node

        return self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp):
        if self.applied or getattr(node, "lineno", -1) != self.target_line:
            return self.generic_visit(node)

        if self.operator == "ARITH" and isinstance(node.op, (ast.Add, ast.Sub)):
            original = copy.deepcopy(node)
            node.op = ast.Sub() if isinstance(node.op, ast.Add) else ast.Add()
            self._record(original, node)
            return node

        return self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant):
        if self.applied or getattr(node, "lineno", -1) != self.target_line:
            return node

        if self.operator == "CONST_OFF_BY_ONE" and isinstance(node.value, int) and not isinstance(node.value, bool):
            original = copy.deepcopy(node)
            node.value = node.value + 1
            self._record(original, node)
            return node
        elif self.operator == "BOOL_NEGATE" and isinstance(node.value, bool):
            original = copy.deepcopy(node)
            node.value = not node.value
            self._record(original, node)
            return node

        return node

    def visit_Return(self, node: ast.Return):
        if self.applied or getattr(node, "lineno", -1) != self.target_line:
            return self.generic_visit(node)

        if self.operator == "RETURN_NONE" and node.value is not None:
            original_value = node.value
            node.value = ast.Constant(value=None)
            self._record(original_value, node.value)
            return node

        return self.generic_visit(node)


def _splice(source: str, span: tuple[int, int, int, int], replacement: str) -> str | None:
    """Replace a single-line expression span (AST byte offsets) and keep the rest of the file intact."""
    start_line, start_col, end_line, end_col = span
    if start_line != end_line:
        return None
    lines = source.splitlines(keepends=True)
    line = lines[start_line - 1].encode("utf-8")
    lines[start_line - 1] = (line[:start_col] + replacement.encode("utf-8") + line[end_col:]).decode("utf-8")
    return "".join(lines)


def generate_mutants(
    files: list[Path],
    coverage_map: dict[str, set[int]] | None = None,
    seed: int = 1337,
    max_mutants: int = 40,
    root: Path | None = None,
) -> list[Mutant]:
    """Deterministically generate AST mutants across covered lines."""
    rng = random.Random(seed)
    operators = ["CMP_FLIP", "ARITH", "CONST_OFF_BY_ONE", "BOOL_NEGATE", "RETURN_NONE"]

    candidates_pool: list[tuple[Path, int, str]] = []

    for file_path in sorted(files, key=lambda p: str(p)):
        rel_str = str(file_path).replace("\\", "/")
        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(file_path))
        except Exception:
            continue

        covered_lines = None
        if coverage_map is not None:
            for k, lines in coverage_map.items():
                if k in rel_str or rel_str in k:
                    covered_lines = lines
                    break
            if covered_lines is None:
                continue

        # Inspect AST nodes for viable mutation points
        for node in ast.walk(tree):
            line = getattr(node, "lineno", None)
            if line is None:
                continue
            if covered_lines is not None and line not in covered_lines:
                continue

            if isinstance(node, ast.Compare):
                candidates_pool.append((file_path, line, "CMP_FLIP"))
            elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub)):
                candidates_pool.append((file_path, line, "ARITH"))
            elif isinstance(node, ast.Constant):
                if isinstance(node.value, int) and not isinstance(node.value, bool):
                    candidates_pool.append((file_path, line, "CONST_OFF_BY_ONE"))
                elif isinstance(node.value, bool):
                    candidates_pool.append((file_path, line, "BOOL_NEGATE"))
            elif isinstance(node, ast.Return) and node.value is not None:
                candidates_pool.append((file_path, line, "RETURN_NONE"))

    rng.shuffle(candidates_pool)

    mutants: list[Mutant] = []
    seen_points: set[tuple[str, int, str]] = set()

    for file_path, line, op in candidates_pool:
        if len(mutants) >= max_mutants:
            break

        key = (str(file_path), line, op)
        if key in seen_points:
            continue
        seen_points.add(key)

        original_code = file_path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(original_code, filename=str(file_path))
            mutator = ASTMutator(target_line=line, operator=op)
            mutator.visit(copy.deepcopy(tree))
            if not mutator.applied or mutator.span is None:
                continue

            mutated_code = _splice(original_code, mutator.span, mutator.replacement)
            if mutated_code is None or mutated_code == original_code:
                continue
            # Ensure it compiles cleanly
            compile(mutated_code, str(file_path), "exec")

            # Generate diff with repo-relative paths, like `git diff`
            rel_name = file_path.relative_to(root).as_posix() if root else file_path.name
            diff_lines = list(
                difflib.unified_diff(
                    original_code.splitlines(keepends=True),
                    mutated_code.splitlines(keepends=True),
                    fromfile=f"a/{rel_name}",
                    tofile=f"b/{rel_name}",
                )
            )
            diff_str = "".join(diff_lines)

            mutants.append(
                Mutant(
                    mutant_id=len(mutants) + 1,
                    file=str(file_path).replace("\\", "/"),
                    line=line,
                    operator=op,
                    original_code=original_code,
                    mutated_code=mutated_code,
                    diff=diff_str,
                )
            )
        except Exception:
            continue

    return mutants
