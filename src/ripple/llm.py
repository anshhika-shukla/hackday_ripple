"""Ollama client wrapper with structured JSON, retry logic, and timing logs."""

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Type

from pydantic import BaseModel, ValidationError

try:
    import ollama
except ImportError:
    ollama = None


def strip_think_blocks(text: str) -> str:
    """Defensively strip reasoning <think>...</think> blocks emitted by models like Qwen3."""
    return re.sub(r"<think>[\s\S]*?</think>", "", text).strip()


class OllamaClient:
    """Wrapper around Ollama with schema validation, retries, and caching."""

    def __init__(
        self,
        model: str | None = None,
        host: str | None = None,
        cache_dir: Path | None = None,
        log_path: Path | None = None,
    ):
        self.model = model or os.getenv("RIPPLE_MODEL", "qwen3:4b-instruct")
        self.host = host or os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.cache_dir = cache_dir or Path(".ripple_cache")
        self.log_path = log_path or Path("runs.jsonl")
        self._client = ollama.Client(host=self.host) if ollama else None

    def _get_cache(self, key: str) -> str | None:
        if not self.cache_dir.exists():
            return None
        cache_file = self.cache_dir / f"{key}.json"
        if cache_file.exists():
            try:
                return cache_file.read_text(encoding="utf-8")
            except Exception:
                return None
        return None

    def _set_cache(self, key: str, value: str) -> None:
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            (self.cache_dir / f"{key}.json").write_text(value, encoding="utf-8")
        except Exception:
            pass

    def _log_run(self, eval_count: int, eval_duration_ns: int, success: bool) -> None:
        try:
            tokens_per_sec = (
                round(eval_count / (eval_duration_ns / 1e9), 2)
                if eval_count and eval_duration_ns > 0
                else 0.0
            )
            record = {
                "timestamp": time.time(),
                "model": self.model,
                "eval_count": eval_count,
                "eval_duration_ns": eval_duration_ns,
                "tokens_per_sec": tokens_per_sec,
                "success": success,
            }
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except Exception:
            pass

    def chat_json(
        self,
        messages: list[dict[str, str]],
        schema: Type[BaseModel],
        retries: int = 2,
        use_cache: bool = True,
        timeout: float = 30.0,
    ) -> tuple[BaseModel | None, str]:
        """
        Send chat prompt to Ollama expecting structured output conforming to Pydantic schema.
        Returns (parsed_pydantic_instance_or_None, status_string).
        Status is one of: "ok", "fallback", "disabled".
        """
        if self._client is None:
            return None, "disabled"

        prompt_str = json.dumps(messages, sort_keys=True)
        cache_key = hashlib.sha256(f"{self.model}:{prompt_str}".encode()).hexdigest()

        if use_cache:
            cached_text = self._get_cache(cache_key)
            if cached_text:
                try:
                    cleaned = strip_think_blocks(cached_text)
                    parsed = schema.model_validate_json(cleaned)
                    return parsed, "ok"
                except Exception:
                    pass

        json_schema = schema.model_json_schema()

        for attempt in range(retries + 1):
            try:
                kwargs = {
                    "model": self.model,
                    "messages": messages,
                    "format": json_schema,
                    "options": {
                        "temperature": 0.0,
                        "num_predict": 200,
                        "num_ctx": 4096,
                    },
                }

                # Try think=False if supported
                try:
                    response = self._client.chat(**kwargs, think=False)
                except (TypeError, Exception):
                    response = self._client.chat(**kwargs)

                if isinstance(response, dict):
                    raw_content = response.get("message", {}).get("content", "")
                    eval_count = response.get("eval_count", 0)
                    eval_duration = response.get("eval_duration", 0)
                else:
                    raw_content = getattr(getattr(response, "message", None), "content", "")
                    eval_count = getattr(response, "eval_count", 0)
                    eval_duration = getattr(response, "eval_duration", 0)

                self._log_run(eval_count, eval_duration, success=True)
                cleaned = strip_think_blocks(raw_content)

                # Parse JSON and validate with schema
                data = json.loads(cleaned)
                parsed = schema.model_validate(data)

                if use_cache:
                    self._set_cache(cache_key, cleaned)

                return parsed, "ok"

            except (ValidationError, json.JSONDecodeError, Exception) as err:
                if attempt == retries:
                    self._log_run(0, 0, success=False)
                    return None, "fallback"
                continue

        return None, "fallback"
