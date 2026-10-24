#!/usr/bin/env bash
# Clone and prepare target repo (pallets/click pinned to 8.1.7)
set -e

mkdir -p targets
if [ ! -d "targets/click" ]; then
    echo "Cloning pallets/click into targets/click..."
    git clone https://github.com/pallets/click.git targets/click
    cd targets/click
    git checkout 8.1.7
    cd ../..
else
    echo "targets/click already exists."
fi

echo "Extracting Graphify code graph for target..."
cd targets/click
if command -v graphify &> /dev/null; then
    graphify extract . --code-only
    graphify cluster-only . --no-label
    graphify export html
else
    echo "Note: 'graphify' CLI not in PATH. Ensure it is installed via 'uv tool install graphifyy'."
fi
cd ../..

echo "✅ Target setup complete."
