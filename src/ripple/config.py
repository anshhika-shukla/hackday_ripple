"""Configuration management for RIPPLE."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RippleConfig:
    model: str = "qwen3:4b-instruct"
    ollama_host: str = "http://localhost:11434"
    target_repo: str = "targets/click"
    graph_path: str = "targets/click/graphify-out/graph.json"
    mode: str = "safe"  # safe | budget
    budget_k: int = 10
    timeout_s: float = 30.0

    @classmethod
    def from_env(cls) -> "RippleConfig":
        return cls(
            model=os.getenv("RIPPLE_MODEL", "qwen3:4b-instruct"),
            ollama_host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            target_repo=os.getenv("TARGET_REPO", "targets/click"),
            graph_path=os.getenv(
                "GRAPH_PATH",
                str(Path(os.getenv("TARGET_REPO", "targets/click")) / "graphify-out" / "graph.json"),
            ),
            mode=os.getenv("RIPPLE_MODE", "safe"),
            budget_k=int(os.getenv("RIPPLE_BUDGET_K", "10")),
            timeout_s=float(os.getenv("RIPPLE_TIMEOUT_S", "30.0")),
        )


config = RippleConfig.from_env()
