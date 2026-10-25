#!/usr/bin/env bash
# Build a browsable Graphify code map (graph.html) for each library in targets/, offline-ready.
# Reads each targets/<lib>/graphify-out/graph.json without changing it (RIPPLE and the eval read it).
# Usage: bash scripts/graph_libs.sh            (all libraries)
#        bash scripts/graph_libs.sh boltons    (one library)
set -e

ROOT="$(pwd)"
VIS="$ROOT/graphify-out/vis-network.min.js"
if [ ! -f "$VIS" ]; then
    curl -sfL https://unpkg.com/vis-network@9.1.6/standalone/umd/vis-network.min.js -o "$VIS"
fi

for dir in ${1:+targets/$1} ${1:-targets/*}; do
    [ -f "$dir/graphify-out/graph.json" ] || continue
    before="$(sha256sum "$dir/graphify-out/graph.json")"
    (cd "$dir" && graphify export html --graph graphify-out/graph.json > /dev/null)
    if [ "$before" != "$(sha256sum "$dir/graphify-out/graph.json")" ]; then
        echo "❌ $dir/graphify-out/graph.json changed; rebuild it with: bash scripts/setup_target.sh"
        exit 1
    fi
    cp "$VIS" "$dir/graphify-out/vis-network.min.js"
    sed -i 's#https://unpkg.com/vis-network@[0-9.]*/standalone/umd/vis-network.min.js#vis-network.min.js#' "$dir/graphify-out/graph.html"
    echo "✅ $dir/graphify-out/graph.html"
done
