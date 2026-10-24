"""End-to-End acceptance tests for RIPPLE CLI and Runner."""

import json
import subprocess
from pathlib import Path

from ripple.cli import main
from ripple.report import Report


def test_e2e_clean_change_exits_0(mini_app_repo: Path):
    """Harmless/passing edit exits with code 0."""
    pricing = mini_app_repo / "pricing.py"
    # Harmless comment addition
    pricing.write_text(pricing.read_text(encoding="utf-8") + "\n# safe comment\n", encoding="utf-8")

    graph_path = Path(__file__).parent / "fixtures" / "graph.json"
    exit_code = main(["check", "--repo", str(mini_app_repo), "--graph", str(graph_path), "--no-llm", "--run"])
    assert exit_code == 0


def test_e2e_seeded_bug_exits_1_and_names_test(mini_app_repo: Path, tmp_path: Path):
    """Seeded bug exits with code 1 and lists failing test in report.json."""
    pricing = mini_app_repo / "pricing.py"
    # Inject bug: break apply_discount
    content = pricing.read_text(encoding="utf-8")
    pricing.write_text(content.replace("1.0 - discount", "1.0 + discount"), encoding="utf-8")

    out_json = tmp_path / "report.json"
    graph_path = Path(__file__).parent / "fixtures" / "graph.json"

    exit_code = main(
        [
            "check",
            "--repo",
            str(mini_app_repo),
            "--graph",
            str(graph_path),
            "--no-llm",
            "--run",
            "--json",
            str(out_json),
        ]
    )
    assert exit_code == 1
    assert out_json.exists()

    report_data = json.loads(out_json.read_text(encoding="utf-8"))
    assert report_data["results"]["failed"] > 0
    assert len(report_data["results"]["failed_ids"]) > 0


def test_dry_run_does_not_execute_tests(mini_app_repo: Path, tmp_path: Path):
    """Default check (without --run) executes 0 tests and exits 0."""
    pricing = mini_app_repo / "pricing.py"
    pricing.write_text(pricing.read_text(encoding="utf-8").replace("1.0 - discount", "1.0 + discount"), encoding="utf-8")

    out_json = tmp_path / "dry_report.json"
    graph_path = Path(__file__).parent / "fixtures" / "graph.json"

    exit_code = main(
        [
            "check",
            "--repo",
            str(mini_app_repo),
            "--graph",
            str(graph_path),
            "--no-llm",
            "--json",
            str(out_json),
        ]
    )
    assert exit_code == 0
    report_data = json.loads(out_json.read_text(encoding="utf-8"))
    assert report_data["results"]["passed"] == 0
    assert report_data["results"]["failed"] == 0


def test_report_json_matches_schema(tmp_path: Path, mini_app_repo: Path):
    """report.json parses and validates against pydantic Report model."""
    pricing = mini_app_repo / "pricing.py"
    pricing.write_text(pricing.read_text(encoding="utf-8") + "\n# safe edit\n", encoding="utf-8")

    out_json = tmp_path / "schema_check.json"
    graph_path = Path(__file__).parent / "fixtures" / "graph.json"

    main(
        [
            "check",
            "--repo",
            str(mini_app_repo),
            "--graph",
            str(graph_path),
            "--no-llm",
            "--json",
            str(out_json),
        ]
    )
    assert out_json.exists()
    report = Report.model_validate_json(out_json.read_text(encoding="utf-8"))
    assert report.mode == "safe"
    assert report.candidates_total >= 0


def test_target_repo_unchanged_after_run(mini_app_repo: Path):
    """Git repository has no untracked artifacts or modified files after runner execution."""
    pricing = mini_app_repo / "pricing.py"
    orig = pricing.read_text(encoding="utf-8")
    pricing.write_text(orig.replace("1.0 - discount", "1.0 + discount"), encoding="utf-8")

    graph_path = Path(__file__).parent / "fixtures" / "graph.json"
    main(["check", "--repo", str(mini_app_repo), "--graph", str(graph_path), "--no-llm", "--run"])

    # Revert the test edit
    pricing.write_text(orig, encoding="utf-8")

    # Verify git status is completely clean
    proc = subprocess.run(["git", "status", "--porcelain"], cwd=str(mini_app_repo), capture_output=True, text=True)
    assert proc.stdout.strip() == "", f"Repo dirty after run: {proc.stdout}"
