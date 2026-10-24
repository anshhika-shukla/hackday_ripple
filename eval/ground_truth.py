"""Ground truth harness: evaluates mutants against full test suite."""

import argparse
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from eval.mutator import generate_mutants


def run_pytest_suite(
    repo_path: Path,
    test_subset: list[str] | None = None,
    timeout_s: float = 120.0,
) -> tuple[list[str], float, bool]:
    """
    Run pytest in repo_path and return (failed_test_ids, duration_s, timed_out).
    """
    start_time = time.time()
    cmd = ["pytest", "-q", "--tb=no"]
    if test_subset:
        cmd.extend(test_subset)

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        duration = time.time() - start_time
        failed_ids = []
        for line in proc.stdout.splitlines():
            if line.startswith("FAILED ") and "::" in line:
                failed_ids.append(line.split()[1])
        return failed_ids, duration, False
    except subprocess.TimeoutExpired:
        duration = time.time() - start_time
        return ["TIMEOUT"], duration, True
    except Exception:
        duration = time.time() - start_time
        return [], duration, False


def run_ground_truth(
    target_repo: str | Path,
    n_mutants: int = 30,
    out_file: str | Path = "eval/data/ground_truth.json",
    timeout_s: float = 120.0,
) -> dict[str, Any]:
    """Run full suite across seeded mutants to establish ground truth."""
    repo = Path(target_repo).resolve()
    out_path = Path(out_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Collect source files
    src_files = [
        f for f in repo.rglob("*.py")
        if "test" not in f.name.lower() and ".venv" not in str(f) and "build" not in str(f)
    ]

    mutants = generate_mutants(src_files, seed=1337, max_mutants=n_mutants)
    mutant_results = []

    for m in mutants:
        target_file = Path(m.file)
        orig_content = m.original_code

        try:
            # Apply mutation
            target_file.write_text(m.mutated_code, encoding="utf-8")
            failed_ids, duration, timed_out = run_pytest_suite(repo, timeout_s=timeout_s)
            killed = len(failed_ids) > 0 or timed_out

            mutant_results.append(
                {
                    "mutant_id": m.mutant_id,
                    "file": m.file,
                    "line": m.line,
                    "operator": m.operator,
                    "diff": m.diff,
                    "killed": killed,
                    "failed_test_ids": failed_ids,
                    "duration_s": round(duration, 2),
                    "timed_out": timed_out,
                }
            )
        finally:
            # Always restore original content
            target_file.write_text(orig_content, encoding="utf-8")

    data = {
        "target_repo": str(repo),
        "total_mutants": len(mutant_results),
        "killed_mutants": sum(1 for m in mutant_results if m["killed"]),
        "mutants": mutant_results,
    }

    out_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def main():
    parser = argparse.ArgumentParser(description="Generate ground truth mutation data.")
    parser.add_argument("--target", default="targets/click", help="Path to target repo")
    parser.add_argument("--n", type=int, default=30, help="Number of mutants to generate")
    parser.add_argument("--out", default="eval/data/ground_truth.json", help="Output path")
    args = parser.parse_args()

    res = run_ground_truth(target_repo=args.target, n_mutants=args.n, out_file=args.out)
    print(f"Ground truth complete: {res['killed_mutants']}/{res['total_mutants']} mutants killed.")


if __name__ == "__main__":
    main()
