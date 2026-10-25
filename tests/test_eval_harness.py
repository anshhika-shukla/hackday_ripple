"""Acceptance tests for Phase 3: Mutation ground truth and evaluation harness."""

from pathlib import Path

from eval.evaluate import compute_metrics
from eval.mutator import generate_mutants


def test_mutator_is_deterministic_with_seed(tmp_path: Path):
    """Same seed produces identical mutant list."""
    f = tmp_path / "calc.py"
    f.write_text("def add(a, b):\n    if a > 0:\n        return a + b\n    return 0\n", encoding="utf-8")

    mutants_1 = generate_mutants([f], seed=1337)
    mutants_2 = generate_mutants([f], seed=1337)

    assert len(mutants_1) == len(mutants_2)
    for m1, m2 in zip(mutants_1, mutants_2):
        assert m1.line == m2.line
        assert m1.operator == m2.operator
        assert m1.mutated_code == m2.mutated_code


def test_mutants_compile(tmp_path: Path):
    """Every generated mutant compiles without syntax errors."""
    f = tmp_path / "sample.py"
    f.write_text("def check(x):\n    val = x + 10\n    return val > 5\n", encoding="utf-8")

    mutants = generate_mutants([f], seed=42)
    assert len(mutants) > 0
    for m in mutants:
        code_obj = compile(m.mutated_code, "<mutant>", "exec")
        assert code_obj is not None


def test_only_covered_lines_mutated(tmp_path: Path):
    """Mutants are strictly generated on covered lines."""
    f = tmp_path / "module.py"
    # lines 1, 2, 3, 4, 5
    f.write_text("def run(a):\n    x = a + 1\n    y = a - 1\n    return x > y\n", encoding="utf-8")

    coverage_map = {str(f).replace("\\", "/"): {2}}  # only line 2 is covered
    mutants = generate_mutants([f], coverage_map=coverage_map, seed=123)

    assert len(mutants) > 0
    for m in mutants:
        assert m.line == 2


def test_restore_after_run(tmp_path: Path):
    """File content is properly restored after mutation execution."""
    from eval.ground_truth import run_ground_truth

    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    original_text = "# keep this comment\ndef add(a, b):\n    return a + b\n"
    (repo / "calc.py").write_text(original_text, encoding="utf-8")
    (repo / "tests" / "test_calc.py").write_text(
        "from calc import add\n\ndef test_add():\n    assert add(2, 3) == 5\n", encoding="utf-8"
    )

    data = run_ground_truth(repo, n_mutants=5, out_file=tmp_path / "gt.json")

    assert (repo / "calc.py").read_text(encoding="utf-8") == original_text
    assert data["total_tests"] == 1
    assert data["killed_mutants"] >= 1
    # Mutations are minimal: the comment survives and the diff touches one line.
    assert all("-# keep this comment" not in m["diff"] for m in data["mutants"])
    assert all(m["failed_test_ids"] == ["tests/test_calc.py::test_add"] for m in data["mutants"] if m["killed"])


def test_scorer_hand_computed_metrics():
    """Catch-rate and selection ratio match hand-computed values on tiny fixture."""
    ground_truth = [
        {"mutant_id": 1, "killed": True, "failed_test_ids": ["test_a"]},
        {"mutant_id": 2, "killed": True, "failed_test_ids": ["test_b"]},
        {"mutant_id": 3, "killed": False, "failed_test_ids": []},
    ]
    # Mutant 1 caught at index 0 (top 1); Mutant 2 not caught
    selected = [
        ["test_a", "test_c"],
        ["test_x", "test_y"],
        ["test_z"],
    ]

    metrics = compute_metrics(selected, ground_truth, total_suite_size=10)
    # 2 killed mutants, 1 caught -> 50.0%
    assert metrics["killed_count"] == 2
    assert metrics["caught_count"] == 1
    assert metrics["catch_rate"] == 50.0
    # top 3 contains test_a for mutant 1
    assert metrics["recall_at_3"] == 50.0
    # Mean selection: (2/10 + 2/10) / 2 = 20.0%
    assert metrics["mean_selection_ratio"] == 20.0
