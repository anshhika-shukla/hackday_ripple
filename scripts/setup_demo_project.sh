#!/usr/bin/env bash
# Set up the live-demo project: examples/canteen -> targets/canteen (its own git repo + Graphify code map).
# Usage: bash scripts/setup_demo_project.sh          (create, or keep an existing copy)
#        bash scripts/setup_demo_project.sh --fresh  (delete and recreate it)
set -e

DEST="targets/canteen"
if [ "$1" = "--fresh" ]; then
    rm -rf "$DEST"
fi

if [ ! -d "$DEST" ]; then
    mkdir -p targets
    cp -r examples/canteen "$DEST"
    printf "[pytest]\ntestpaths = tests\n" > "$DEST/pytest.ini"
    printf "graphify-out/\n__pycache__/\n.pytest_cache/\n" > "$DEST/.gitignore"
    git -C "$DEST" init -q
    git -C "$DEST" add .
    git -C "$DEST" -c user.name=ripple -c user.email=ripple@localhost commit -qm "canteen baseline"
    (cd "$DEST" && graphify extract . --code-only > /dev/null)
    bash scripts/graph_libs.sh canteen
else
    echo "$DEST already exists (use --fresh to recreate it)."
fi
echo "✅ Demo project ready: $DEST"
echo "   Edit a file there (don't commit), then: .venv/bin/python -m ripple.cli check --repo $DEST --run"
echo "   Undo your edit with: git -C $DEST checkout -- ."
