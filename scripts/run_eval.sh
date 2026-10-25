#!/usr/bin/env bash
# Reproduce the evaluation numbers: ground truth (seeded mutants) + strategies A / B / C.
# Usage: N=60 bash scripts/run_eval.sh boltons      (or: click, mini_app)
set -euo pipefail

TARGET="${1:-click}"
N="${N:-40}"
PY="${PY:-.venv/bin/python}"
GT="eval/data/ground_truth_${TARGET}.json"
GRAPH="targets/${TARGET}/graphify-out/graph.json"
OUT="eval/results/${TARGET}"
SRC_ARGS=()
case "$TARGET" in
    click)   SRC_ARGS=(--src src) ;;
    boltons) SRC_ARGS=(--src boltons --workers 8) ;;
esac

# Click 8.1.7's own tests trip a pytest 9 deprecation that is unrelated to RIPPLE.
export PYTEST_ADDOPTS="${PYTEST_ADDOPTS:-} -W ignore::pytest.PytestRemovedIn10Warning"

if [ ! -f "$GT" ]; then
    "$PY" -m eval.ground_truth --target "targets/${TARGET}" "${SRC_ARGS[@]}" --n "$N" --out "$GT"
fi

"$PY" -m eval.evaluate --strategy A --mutants "$N" --gt "$GT" --graph "$GRAPH" --out-dir "$OUT"
"$PY" -m eval.evaluate --strategy B --no-closure --mutants "$N" --gt "$GT" --graph "$GRAPH" --out-dir "$OUT"
"$PY" -m eval.evaluate --strategy B --mutants "$N" --gt "$GT" --graph "$GRAPH" --out-dir "$OUT"
# 3 repeated runs of the LLM strategy without the response cache (reliability evidence)
"$PY" -m eval.evaluate --strategy C --mutants "$N" --runs 3 --no-cache --gt "$GT" --graph "$GRAPH" --out-dir "$OUT"
