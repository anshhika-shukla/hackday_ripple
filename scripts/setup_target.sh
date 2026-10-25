#!/usr/bin/env bash
# Prepare evaluation/demo targets in targets/ (gitignored):
#   targets/click     pallets/click pinned to 8.1.7, installed editable so mutants take effect
#   targets/boltons   mahmoud/boltons pinned to 26.2.0 (main demo and evaluation target)
#   targets/mini_app  copy of tests/fixtures/mini_app as its own git repo (tiny demo target)
# Each target gets a real Graphify code graph in graphify-out/graph.json.
set -e

PY="${PY:-.venv/bin/python}"
mkdir -p targets

if [ ! -d "targets/click" ]; then
    echo "Cloning pallets/click into targets/click..."
    git clone https://github.com/pallets/click.git targets/click
    git -C targets/click -c advice.detachedHead=false checkout 8.1.7
else
    echo "targets/click already exists."
fi
if command -v uv &> /dev/null; then
    uv pip install --python "$PY" -e targets/click
else
    "$PY" -m pip install -e targets/click
fi

if [ ! -d "targets/boltons" ]; then
    echo "Cloning mahmoud/boltons into targets/boltons..."
    git clone https://github.com/mahmoud/boltons.git targets/boltons
    git -C targets/boltons -c advice.detachedHead=false checkout 26.2.0
else
    echo "targets/boltons already exists."
fi

if [ ! -d "targets/mini_app" ]; then
    echo "Creating targets/mini_app from tests/fixtures/mini_app..."
    cp -r tests/fixtures/mini_app targets/mini_app
    printf "[pytest]\n" > targets/mini_app/pytest.ini
    printf "graphify-out/\n__pycache__/\n" > targets/mini_app/.gitignore
    git -C targets/mini_app init -q
    git -C targets/mini_app add .
    git -C targets/mini_app -c user.name=ripple -c user.email=ripple@localhost commit -qm "mini_app baseline"
else
    echo "targets/mini_app already exists."
fi

if ! command -v graphify &> /dev/null; then
    echo "Note: 'graphify' CLI not in PATH. Install it with 'uv tool install graphifyy', then rerun."
    exit 1
fi
for t in boltons click mini_app; do
    echo "Extracting Graphify code graph for targets/$t..."
    (cd "targets/$t" && graphify extract . --code-only)
done

echo "✅ Target setup complete."
