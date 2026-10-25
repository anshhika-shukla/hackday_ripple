"""Ground truth harness: evaluates mutants against full test suite."""

import sys
import argparse
import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from eval.mutator import generate_mutants

# Never mutate tests or non-library code; mutants there cannot be killed by the suite.
SKIP_DIRS = {"tests", "test", "docs", "examples", "graphify-out", ".venv", "venv", "build", ".git", ".work"}


def _pytest_env() -> dict[str, str]:
    # Keep the target repo clean: no bytecode files.
    return {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}


def run_pytest_suite(
    repo_path: Path,
    test_subset: list[str] | None = None,
    timeout_s: float = 120.0,
    workers: int = 0,
) -> tuple[list[str], float, bool]:
    """
    Run pytest in repo_path and return (failed_test_ids, duration_s, timed_out).
    """
    start_time = time.time()
    cmd = [sys.executable, "-m", "pytest", "-q", "--tb=no", "-rfE", "-p", "no:cacheprovider"]
    if workers:
        cmd.extend(["-n", str(workers)])  # pytest-xdist
    if test_subset:
        cmd.extend(test_subset)

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=timeout_s,
            env=_pytest_env(),
        )
        duration = time.time() - start_time
        failed_ids = re.findall(r"^(?:FAILED|ERROR) (\S+)", proc.stdout, flags=re.MULTILINE)
        return failed_ids, duration, False
    except subprocess.TimeoutExpired:
        duration = time.time() - start_time
        return ["TIMEOUT"], duration, True


def collect_test_ids(repo_path: Path) -> list[str]:
    """All pytest node ids in the repo."""
    cmd = [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"]
    proc = subprocess.run(cmd, cwd=str(repo_path), capture_output=True, text=True, env=_pytest_env())
    return [line.strip() for line in proc.stdout.splitlines() if "::" in line]


def covered_lines(repo: Path, src: str | None = None) -> dict[str, set[int]]:
    """Lines executed by the suite, per absolute file path, so mutants land where tests can kill them."""
    with tempfile.TemporaryDirectory(prefix="ripple_cov_") as tmp:
        data_file, json_file = Path(tmp) / ".coverage", Path(tmp) / "coverage.json"
        run = [sys.executable, "-m", "coverage", "run", f"--data-file={data_file}", f"--source={src or '.'}",
               "-m", "pytest", "-q", "-p", "no:cacheprovider"]
        subprocess.run(run, cwd=str(repo), capture_output=True, text=True, env=_pytest_env())
        report = [sys.executable, "-m", "coverage", "json", f"--data-file={data_file}", "-o", str(json_file)]
        subprocess.run(report, cwd=str(repo), capture_output=True, text=True, env=_pytest_env())
        if not json_file.exists():
            return {}
        files = json.loads(json_file.read_text(encoding="utf-8"))["files"]
    return {str((repo / name).resolve()): set(info["executed_lines"]) for name, info in files.items()}


def find_source_files(repo: Path, src: str | None = None) -> list[Path]:
    """Library source files to mutate (everything outside test/docs/example dirs by default)."""
    root = repo / src if src else repo
    files = []
    for f in sorted(root.rglob("*.py")):
        rel_parts = f.relative_to(repo).parts
        if any(part in SKIP_DIRS for part in rel_parts[:-1]):
            continue
        if f.name.startswith("test_") or f.name.endswith("_test.py") or f.name in ("conftest.py", "setup.py"):
            continue
        files.append(f)
    return files


def run_ground_truth(
    target_repo: str | Path,
    n_mutants: int = 30,
    out_file: str | Path = "eval/data/ground_truth.json",
    timeout_s: float = 120.0,
    src: str | None = None,
    covered_only: bool = True,
    workers: int = 0,
) -> dict[str, Any]:
    """Run full suite across seeded mutants to establish ground truth."""
    repo = Path(target_repo).resolve()
    out_path = Path(out_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Clean baseline: suite size, runtime, and tests that already fail without any mutation.
    all_test_ids = collect_test_ids(repo)
    baseline_failed, baseline_s, _ = run_pytest_suite(repo, timeout_s=timeout_s)
    baseline_set = set(baseline_failed)
    if workers:
        # Parallel runs must agree with the serial baseline, or xdist is not safe for this suite.
        parallel_failed, _, _ = run_pytest_suite(repo, timeout_s=timeout_s, workers=workers)
        if set(parallel_failed) != baseline_set:
            print(f"pytest-xdist changes results for this suite ({len(parallel_failed)} vs {len(baseline_set)} failures); running serially")
            workers = 0

    coverage_map = covered_lines(repo, src) if covered_only else None
    mutants = generate_mutants(
        find_source_files(repo, src), coverage_map=coverage_map, seed=1337, max_mutants=n_mutants, root=repo
    )
    mutant_results = []

    for m in mutants:
        target_file = Path(m.file)
        try:
            target_file.write_text(m.mutated_code, encoding="utf-8")
            failed_ids, duration, timed_out = run_pytest_suite(repo, timeout_s=timeout_s, workers=workers)
            # A mutant is only "killed" by tests that pass on the clean code.
            failed_ids = [t for t in failed_ids if t not in baseline_set]
            killed = len(failed_ids) > 0 or timed_out

            mutant_results.append(
                {
                    "mutant_id": m.mutant_id,
                    "file": target_file.relative_to(repo).as_posix(),
                    "line": m.line,
                    "operator": m.operator,
                    "diff": m.diff,
                    "killed": killed,
                    "failed_test_ids": failed_ids,
                    "duration_s": round(duration, 2),
                    "timed_out": timed_out,
                }
            )
            print(f"mutant {m.mutant_id:>3} {m.operator:<16} {mutant_results[-1]['file']}:{m.line} killed={killed}")
        finally:
            # Always restore original content
            target_file.write_text(m.original_code, encoding="utf-8")

    data = {
        "target_repo": str(repo),
        "total_tests": len(all_test_ids),
        "all_test_ids": all_test_ids,
        "baseline_failures": baseline_failed,
        "full_suite_duration_s": round(baseline_s, 2),
        "covered_only": covered_only,
        "total_mutants": len(mutant_results),
        "killed_mutants": sum(1 for m in mutant_results if m["killed"]),
        "mutants": mutant_results,
    }

    out_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def main():
    parser = argparse.ArgumentParser(description="Generate ground truth mutation data.")
    parser.add_argument("--target", default="targets/click", help="Path to target repo")
    parser.add_argument("--src", default=None, help="Sub-directory of the target to mutate (default: all library code)")
    parser.add_argument("--n", type=int, default=30, help="Number of mutants to generate")
    parser.add_argument("--out", default="eval/data/ground_truth_click.json", help="Output path")
    parser.add_argument("--all-lines", action="store_true", help="Also mutate lines no test executes")
    parser.add_argument("--workers", type=int, default=0, help="Run each suite with pytest-xdist -n WORKERS")
    args = parser.parse_args()

    res = run_ground_truth(
        target_repo=args.target, n_mutants=args.n, out_file=args.out, src=args.src,
        covered_only=not args.all_lines, workers=args.workers,
    )
    print(
        f"Ground truth complete: {res['killed_mutants']}/{res['total_mutants']} mutants killed. "
        f"Suite: {res['total_tests']} tests in {res['full_suite_duration_s']}s"
    )


if __name__ == "__main__":
    main()
