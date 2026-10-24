"""Pytest fixtures for RIPPLE tests."""

import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def mini_app_repo(tmp_path: Path) -> Path:
    """Creates a temporary git repository containing mini_app fixtures."""
    fixture_dir = Path(__file__).parent / "fixtures" / "mini_app"
    target_dir = tmp_path / "mini_app_repo"
    target_dir.mkdir(parents=True, exist_ok=True)

    # Copy files
    for item in fixture_dir.iterdir():
        if item.is_dir():
            shutil.copytree(item, target_dir / item.name)
        else:
            shutil.copy2(item, target_dir / item.name)

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=target_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "ripple@example.com"],
        cwd=target_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Ripple Test"],
        cwd=target_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "add", "."], cwd=target_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=target_dir,
        check=True,
        capture_output=True,
    )

    return target_dir
