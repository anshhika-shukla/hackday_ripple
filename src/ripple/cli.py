"""Command Line Interface for RIPPLE."""

import argparse
import json
import os
import stat
import subprocess
import sys
import time
from pathlib import Path

from ripple.config import config
from ripple.diffmap import parse_diff
from ripple.graphio import load_graph
from ripple.impact import baseline_ranking_b, compute_impact
from ripple.llm import OllamaClient
from ripple.report import Report, generate_brief
from ripple.runner import count_suite_tests, run_tests
from ripple.triage import select_and_rank_tests

try:
    from rich.console import Console
    from rich.markdown import Markdown
    console = Console()
except ImportError:
    console = None


def get_diff_text(repo: Path, base: str = "HEAD") -> str:
    """Fetch raw git diff text."""
    try:
        cmd = ["git", "-C", str(repo), "diff", "-U0", base]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return proc.stdout
    except Exception:
        return ""


def find_graph_file(repo: Path, explicit_path: str | None) -> Path | None:
    """Find graph.json in explicit location, repo graphify-out, or default fallback."""
    if explicit_path:
        p = Path(explicit_path)
        if p.exists():
            return p
        resolved = repo / explicit_path
        if resolved.exists():
            return resolved

    # Search standard paths
    candidates = [
        repo / "graphify-out" / "graph.json",
        repo / "tests" / "fixtures" / "graph.json",
        Path("tests/fixtures/graph.json"),
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def handle_check(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    base = args.base
    mode = args.mode
    budget_k = args.k
    no_llm = args.no_llm
    do_run = args.run
    json_out = args.json_out

    # 1. Parse diff
    start_graph = time.time()
    diff_text = get_diff_text(repo, base)
    changed_symbols = parse_diff(repo=repo, base=base, patch_text=diff_text if diff_text else None)

    # 2. Locate and load graph
    graph_path = find_graph_file(repo, args.graph)
    if not graph_path:
        print(f"Error: Could not locate graph.json. Run 'graphify extract .' first or specify --graph.", file=sys.stderr)
        return 2

    graph = load_graph(graph_path)
    graph_duration = time.time() - start_graph

    # 3. LLM client & selection
    start_llm = time.time()
    client = OllamaClient(model=config.model, host=config.ollama_host)
    selected, triage, guardrails, llm_status = select_and_rank_tests(
        graph=graph,
        changed_symbols=changed_symbols,
        diff_text=diff_text,
        client=client,
        mode=mode,
        budget_k=budget_k,
        no_llm=no_llm,
        use_cache=not args.no_cache,
    )
    llm_duration = time.time() - start_llm

    # 4. Optional Test Execution
    start_tests = time.time()
    test_ids = [c.test_id for c in selected]
    results_dict = {"passed": 0, "failed": 0, "skipped": 0, "failed_ids": []}

    if do_run and test_ids:
        res = run_tests(test_ids=test_ids, repo_path=repo, timeout_s=config.timeout_s)
        results_dict = {
            "passed": res.passed,
            "failed": res.failed,
            "skipped": res.skipped,
            "failed_ids": res.failed_ids,
        }
    tests_duration = time.time() - start_tests

    timing = {
        "graph_s": round(graph_duration, 3),
        "llm_s": round(llm_duration, 3),
        "tests_s": round(tests_duration, 3),
    }
    if do_run and args.baseline:
        # Measure the full suite for an honest "time saved" comparison.
        full = run_tests(test_ids=["."], repo_path=repo, timeout_s=config.timeout_s * 10)
        timing["full_suite_s"] = full.duration_s

    # 5. Build report
    total_candidates = len(selected) if llm_status == "skipped_deterministic" else len(compute_impact(graph, changed_symbols)[0])
    report = Report(
        mode=mode,
        model=config.model,
        llm_status=llm_status,
        changed=[s.model_dump() for s in changed_symbols],
        candidates_total=total_candidates,
        selected=len(selected),
        suite_total=count_suite_tests(repo),
        results=results_dict,
        timing=timing,
        tokens_per_sec=round(sum(client.token_rates) / len(client.token_rates), 2) if client.token_rates else 0.0,
        guardrails_fired=guardrails,
        triage=triage.model_dump(include={"change_kind", "risk", "summary"}) if triage else {},
    )

    brief_md = generate_brief(report)
    if console:
        console.print(Markdown(brief_md))
    else:
        print(brief_md)

    if json_out:
        Path(json_out).write_text(report.model_dump_json(indent=2), encoding="utf-8")

    if do_run and results_dict["failed"] > 0:
        return 1
    return 0


def handle_select(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    diff_text = get_diff_text(repo, args.base)
    changed_symbols = parse_diff(repo=repo, base=args.base, patch_text=diff_text if diff_text else None)

    graph_path = find_graph_file(repo, args.graph)
    if not graph_path:
        print(f"Error: Could not locate graph.json.", file=sys.stderr)
        return 2

    graph = load_graph(graph_path)
    candidates, _ = compute_impact(graph, changed_symbols)
    ranked = baseline_ranking_b(candidates)

    output = [c.model_dump() for c in ranked]
    print(json.dumps(output, indent=2))
    return 0


def handle_install_hook(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    hook_dir = repo / ".git" / "hooks"
    if not hook_dir.exists():
        print(f"Error: .git/hooks directory not found at {repo}", file=sys.stderr)
        return 2

    hook_file = hook_dir / "pre-push"
    # Compare against what the remote already has (committed changes are what get pushed),
    # and call RIPPLE through the interpreter it is installed in, so no activated venv is needed.
    hook_script = f"""#!/usr/bin/env bash
# RIPPLE pre-push hook: run selected tests offline
echo "🌊 RIPPLE pre-push test selection..."
BASE=$(git rev-parse --abbrev-ref --symbolic-full-name @{{u}} 2>/dev/null || echo HEAD~1)
"{sys.executable}" -m ripple.cli check --repo . --base "$BASE" --run --mode budget --k 10
EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
    echo "❌ RIPPLE caught test failures. Push aborted."
    exit $EXIT_CODE
fi
exit 0
"""
    hook_file.write_text(hook_script, encoding="utf-8")
    try:
        hook_file.chmod(hook_file.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    except Exception:
        pass

    print(f"✅ RIPPLE pre-push hook installed at {hook_file}")
    return 0


def handle_draft_tests(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    from ripple.diffmap import parse_diff
    from ripple.draft import draft_pytest_code, find_uncovered_symbols, verify_drafted_test_on_baseline
    from ripple.graphio import load_graph

    diff_text = get_diff_text(repo)
    changed_symbols = parse_diff(repo=repo, patch_text=diff_text if diff_text else None)

    graph_path = find_graph_file(repo, args.graph)
    if not graph_path:
        print("Error: graph.json not found.", file=sys.stderr)
        return 2

    graph = load_graph(graph_path)
    uncovered = find_uncovered_symbols(graph, changed_symbols)
    if not uncovered:
        print("All changed symbols have existing covering test cases.")
        return 0

    client = OllamaClient(model=config.model, host=config.ollama_host)
    print(f"Found {len(uncovered)} uncovered symbol(s). Drafting candidate tests...")

    for sym in uncovered:
        code = draft_pytest_code(sym, client)
        passed = verify_drafted_test_on_baseline(code, repo)
        status_msg = "✅ Passed on baseline (Adopted)" if passed else "❌ Discarded (Failed baseline check)"
        print(f"Symbol: {sym.qualname} -> {status_msg}")
        if passed and args.out:
            Path(args.out).write_text(code, encoding="utf-8")
            print(f"Draft written to {args.out}")

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ripple",
        description="RIPPLE: Offline change-impact and test-selection agent.",
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Sub-commands")

    # check subcommand
    check_parser = subparsers.add_parser("check", help="Triage changes, select tests, and optionally run them")
    check_parser.add_argument("--repo", default=".", help="Path to git repository")
    check_parser.add_argument("--base", default="HEAD", help="Base commit or branch for diff")
    check_parser.add_argument("--graph", default=None, help="Path to Graphify graph.json")
    check_parser.add_argument("--mode", choices=["safe", "budget"], default="safe", help="Execution mode")
    check_parser.add_argument("--k", type=int, default=10, help="Candidate budget for budget mode")
    check_parser.add_argument("--no-llm", action="store_true", help="Bypass LLM and use graph ranking only")
    check_parser.add_argument("--no-cache", action="store_true", help="Ask the model again instead of reusing a cached answer")
    check_parser.add_argument("--baseline", action="store_true", help="With --run, also time the full suite to report time saved")
    check_parser.add_argument("--run", action="store_true", help="Execute the selected tests (default is dry-run)")
    check_parser.add_argument("--json", dest="json_out", default=None, help="Path to export report.json")

    # select subcommand
    select_parser = subparsers.add_parser("select", help="Select candidate tests based on code graph")
    select_parser.add_argument("--repo", default=".", help="Path to git repository")
    select_parser.add_argument("--base", default="HEAD", help="Base commit or branch for diff")
    select_parser.add_argument("--graph", default=None, help="Path to Graphify graph.json")
    select_parser.add_argument("--no-llm", action="store_true", help="Bypass LLM and use graph ranking only")

    # map subcommand (handled in Phase 6)
    map_parser = subparsers.add_parser("map", help="Generate standalone HTML/SVG ripple map")
    map_parser.add_argument("--repo", default=".", help="Path to git repository")
    map_parser.add_argument("--graph", default=None, help="Path to Graphify graph.json")
    map_parser.add_argument("--out", default="ripple_map.html", help="Output HTML file path")
    map_parser.add_argument("--report", default=None, help="report.json from `ripple check --json`, to show results on the map")

    # draft-tests subcommand (stretch feature)
    draft_parser = subparsers.add_parser("draft-tests", help="Draft pytest tests for untested changed symbols")
    draft_parser.add_argument("--repo", default=".", help="Path to git repository")
    draft_parser.add_argument("--graph", default=None, help="Path to Graphify graph.json")
    draft_parser.add_argument("--out", default=None, help="Output test file path")

    # install-hook subcommand
    hook_parser = subparsers.add_parser("install-hook", help="Install RIPPLE as a git pre-push hook")
    hook_parser.add_argument("--repo", default=".", help="Path to git repository")

    return parser


def main(args=None) -> int:
    parser = build_parser()
    parsed = parser.parse_args(args)

    if not parsed.subcommand:
        parser.print_help()
        return 0

    if parsed.subcommand == "check":
        return handle_check(parsed)
    elif parsed.subcommand == "select":
        return handle_select(parsed)
    elif parsed.subcommand == "install-hook":
        return handle_install_hook(parsed)
    elif parsed.subcommand == "map":
        from ripple.ripplemap import generate_map_cli
        return generate_map_cli(parsed)
    elif parsed.subcommand == "draft-tests":
        return handle_draft_tests(parsed)

    return 0


if __name__ == "__main__":
    sys.exit(main())
