"""Smoke test script for local Ollama LLM integration."""

import json
import os
import re
import sys
import time

try:
    import ollama
except ImportError:
    print("Error: 'ollama' Python package not installed. Run 'pip install ollama'.", file=sys.stderr)
    sys.exit(1)


def strip_think_blocks(text: str) -> str:
    """Strip <think>...</think> blocks emitted by reasoning models like Qwen3."""
    return re.sub(r"<think>[\s\S]*?</think>", "", text).strip()


def smoke_test(model: str | None = None, host: str | None = None) -> bool:
    model = model or os.getenv("RIPPLE_MODEL", "qwen3:4b-instruct")
    host = host or os.getenv("OLLAMA_HOST", "http://localhost:11434")

    # JSON schema for structured response
    schema = {
        "type": "object",
        "properties": {
            "status": {"type": "string"},
            "message": {"type": "string"},
            "model_tested": {"type": "string"},
        },
        "required": ["status", "message", "model_tested"],
    }

    prompt = (
        "Respond with a brief greeting acknowledging this smoke test. /no_think"
    )

    client = ollama.Client(host=host)

    try:
        # Prepare chat arguments
        kwargs = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a software testing agent. Respond ONLY in valid JSON matching the schema.",
                },
                {"role": "user", "content": prompt},
            ],
            "format": schema,
            "options": {"temperature": 0.0},
        }

        # Try passing think=False for Ollama versions supporting it
        try:
            response = client.chat(**kwargs, think=False)
        except (TypeError, Exception):
            response = client.chat(**kwargs)

        # Extract message content
        content = ""
        if isinstance(response, dict):
            content = response.get("message", {}).get("content", "")
            eval_count = response.get("eval_count", 0)
            eval_duration = response.get("eval_duration", 0)
        else:
            content = getattr(getattr(response, "message", None), "content", "")
            eval_count = getattr(response, "eval_count", 0)
            eval_duration = getattr(response, "eval_duration", 0)

        cleaned_content = strip_think_blocks(content)

        # Validate JSON
        json_valid = False
        try:
            parsed = json.loads(cleaned_content)
            if isinstance(parsed, dict) and "status" in parsed:
                json_valid = True
        except Exception:
            json_valid = False

        # Calculate tokens per second
        # eval_duration is in nanoseconds in Ollama API
        if eval_count and eval_duration and eval_duration > 0:
            tokens_per_sec = round(eval_count / (eval_duration / 1e9), 2)
        else:
            tokens_per_sec = 0.0

        print(f"ok model={model} json_valid={json_valid} tokens_per_sec={tokens_per_sec}")
        return json_valid

    except Exception as e:
        print(f"FAILED model={model} error={e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    success = smoke_test()
    sys.exit(0 if success else 1)
