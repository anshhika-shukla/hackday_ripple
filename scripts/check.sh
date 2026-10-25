#!/usr/bin/env bash
# Check your own edited code with RIPPLE and show the result on the dashboard ("Your latest check").
# Usage: bash scripts/check.sh /path/to/project [extra ripple check flags, e.g. --no-llm]
# Needs: a git repo with uncommitted changes, pytest tests, and graphify-out/graph.json
#        (cd /path/to/project && graphify extract . --code-only)
set -e

PY="${PY:-.venv/bin/python}"
REPO="${1:?Usage: bash scripts/check.sh /path/to/project [ripple check flags]}"
shift
OUT="runs/latest"

mkdir -p "$OUT"
rm -f "$OUT/report.json" "$OUT/map.html" "$OUT/meta.json"

set +e
"$PY" -m ripple.cli check --repo "$REPO" --run --json "$OUT/report.json" "$@"
EXIT_CODE=$?
set -e
if [ ! -f "$OUT/report.json" ]; then
    echo "No report written (exit code $EXIT_CODE); see the message above."
    exit "$EXIT_CODE"
fi

"$PY" -m ripple.cli map --repo "$REPO" --report "$OUT/report.json" --out "$OUT/map.html"
"$PY" -c "import json, sys, time, pathlib; pathlib.Path(sys.argv[1]).write_text(json.dumps({'repo': str(pathlib.Path(sys.argv[2]).resolve()), 'checked_at': time.strftime('%Y-%m-%d %H:%M'), 'exit_code': int(sys.argv[3])}))" \
    "$OUT/meta.json" "$REPO" "$EXIT_CODE"

echo ""
echo "Dashboard: python scripts/serve.py, then open http://localhost:8000/#latest"
exit "$EXIT_CODE"
