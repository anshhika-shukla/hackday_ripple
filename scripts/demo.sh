#!/usr/bin/env bash
# RIPPLE demo: plant a one-line bug in a target repo, let RIPPLE select and run the impacted
# tests, show the brief and ripple map, then restore the target.
# Usage: bash scripts/demo.sh            (boltons, the main demo)
#        bash scripts/demo.sh mini_app   (tiny shop app)
# Prerequisite: bash scripts/setup_target.sh
set -e

PY="${PY:-.venv/bin/python}"
TARGET="${1:-boltons}"
TARGET_DIR="targets/$TARGET"
PATCH="$(pwd)/scripts/bugs/${TARGET}_demo.patch"

if [ ! -f "$TARGET_DIR/graphify-out/graph.json" ]; then
    echo "Missing $TARGET_DIR/graphify-out/graph.json. Run: bash scripts/setup_target.sh"
    exit 2
fi
if [ -n "$(git -C "$TARGET_DIR" status --porcelain --untracked-files=no)" ]; then
    echo "$TARGET_DIR has uncommitted changes; restore it first (git -C $TARGET_DIR checkout -- .)"
    exit 2
fi

restore() { git -C "$TARGET_DIR" checkout -q -- .; }
trap restore EXIT

echo "======================================================================"
echo "🌊 RIPPLE Demo: Offline change-impact & test-selection agent"
echo "======================================================================"

# Load the model into memory first so the timed run measures inference, not model loading.
MODEL="${RIPPLE_MODEL:-qwen3:4b-instruct}"
curl -s -m 120 "${OLLAMA_HOST:-http://localhost:11434}/api/generate" \
    -d "{\"model\": \"$MODEL\", \"keep_alive\": \"30m\"}" > /dev/null || echo "(Ollama not reachable: RIPPLE will fall back to graph-only ranking)"

echo ""
echo "[Step 1] Planting a one-line bug in $TARGET_DIR"
git -C "$TARGET_DIR" apply "$PATCH"
git -C "$TARGET_DIR" --no-pager diff

echo ""
echo "[Step 2] ripple check --run --baseline --no-cache (select, ask the local LLM, run, compare to full suite)"
echo "----------------------------------------------------------------------"
set +e
"$PY" -m ripple.cli check --repo "$TARGET_DIR" --run --baseline --no-cache --json ripple_report.json
EXIT_CODE=$?
set -e
echo "ripple exit code: $EXIT_CODE (1 = selected tests caught a regression)"

echo ""
echo "[Step 3] Generating ripple map: ripple_map.html"
"$PY" -m ripple.cli map --repo "$TARGET_DIR" --report ripple_report.json --out ripple_map.html
if command -v explorer.exe &> /dev/null; then
    explorer.exe ripple_map.html 2>/dev/null || true   # WSL: open in the Windows browser
elif command -v xdg-open &> /dev/null; then
    xdg-open ripple_map.html 2>/dev/null || true
elif command -v open &> /dev/null; then
    open ripple_map.html 2>/dev/null || true
fi
# Keep this library's demo for the results page (results.html has one tab per library).
mkdir -p "eval/results/$TARGET"
cp ripple_report.json "eval/results/$TARGET/demo_report.json"
cp ripple_map.html "eval/results/$TARGET/demo_map.html"

echo ""
echo "[Step 4] Restoring target"
restore
trap - EXIT
git -C "$TARGET_DIR" status --short --untracked-files=no

echo ""
echo "[Step 5] Updating results page: results.html"
"$PY" scripts/build_results.py
echo "✅ Demo complete. Target restored."
