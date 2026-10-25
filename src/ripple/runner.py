"""Test runner: executes selected pytest tests safely in read-only mode."""

import os
import re
import sys
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TestResult:
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    failed_ids: list[str] = field(default_factory=list)
    duration_s: float = 0.0
    exit_code: int = 0
    timed_out: bool = False


def run_tests(
    test_ids: list[str],
    repo_path: Path,
    timeout_s: float = 60.0,
    junit_xml_path: Path | None = None,
) -> TestResult:
    """
    Run selected pytest subset using --junitxml.
    Guardrail G6: Isolated, read-only on repo code, strict timeout.
    """
    if not test_ids:
        return TestResult(passed=0, failed=0, skipped=0, failed_ids=[], duration_s=0.0, exit_code=0)

    repo = Path(repo_path).resolve()
    # G6: nothing is written into the target repo (no junit file, bytecode or pytest cache).
    xml_path = junit_xml_path or Path(tempfile.mkdtemp(prefix="ripple_")) / "junit.xml"
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}

    cmd = [sys.executable, "-m", "pytest", "-q", "-rfE", "-p", "no:cacheprovider", f"--junitxml={xml_path}"] + test_ids
    start_time = time.time()

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=timeout_s,
            env=env,
        )
        duration = time.time() - start_time
        exit_code = proc.returncode
        timed_out = False
    except subprocess.TimeoutExpired:
        duration = time.time() - start_time
        exit_code = 2
        timed_out = True
        return TestResult(
            passed=0,
            failed=len(test_ids),
            skipped=0,
            failed_ids=["TIMEOUT"],
            duration_s=round(duration, 2),
            exit_code=exit_code,
            timed_out=True,
        )
    except Exception as e:
        duration = time.time() - start_time
        return TestResult(
            passed=0,
            failed=1,
            skipped=0,
            failed_ids=[f"ExecutionError: {e}"],
            duration_s=round(duration, 2),
            exit_code=2,
            timed_out=False,
        )

    # Parse JUnit XML
    passed = 0
    failed = 0
    skipped = 0
    failed_ids: list[str] = []

    if xml_path.exists():
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            for testcase in root.iter("testcase"):
                classname = testcase.get("classname", "")
                name = testcase.get("name", "")
                test_id = f"{classname}::{name}"

                has_failure = testcase.find("failure") is not None or testcase.find("error") is not None
                has_skip = testcase.find("skipped") is not None

                if has_failure:
                    failed += 1
                    failed_ids.append(test_id)
                elif has_skip:
                    skipped += 1
                else:
                    passed += 1
        except Exception:
            # Fallback to exit_code
            if exit_code == 0:
                passed = len(test_ids)
            else:
                failed = 1
                failed_ids = [test_ids[0]]
        finally:
            try:
                xml_path.unlink()
            except Exception:
                pass
    else:
        if exit_code == 0:
            passed = len(test_ids)
        else:
            failed = 1
            failed_ids = test_ids[:1]

    # Prefer real pytest node ids from the "FAILED <id> - ..." summary lines over junit classnames.
    summary_ids = re.findall(r"^(?:FAILED|ERROR) (\S+)", proc.stdout, flags=re.MULTILINE)
    if summary_ids:
        failed_ids = summary_ids

    return TestResult(
        passed=passed,
        failed=failed,
        skipped=skipped,
        failed_ids=failed_ids,
        duration_s=round(duration, 2),
        exit_code=0 if failed == 0 else 1,
        timed_out=timed_out,
    )


def count_suite_tests(repo_path: Path, timeout_s: float = 60.0) -> int:
    """Number of tests pytest collects in the repo (0 if collection fails)."""
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    cmd = [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"]
    try:
        proc = subprocess.run(cmd, cwd=str(repo_path), capture_output=True, text=True, timeout=timeout_s, env=env)
    except Exception:
        return 0
    match = re.search(r"(\d+) tests? collected", proc.stdout)
    if match:
        return int(match.group(1))
    return sum(1 for line in proc.stdout.splitlines() if "::" in line)
