#!/usr/bin/env bash
# Regenerate RIPPLE's own Graphify graph and make graph.html work offline
# (Graphify's HTML loads vis-network from unpkg; we serve a local copy instead).
set -e

graphify extract . --code-only
graphify cluster-only . --no-label
graphify export html

if [ ! -f graphify-out/vis-network.min.js ]; then
    curl -sfL https://unpkg.com/vis-network@9.1.6/standalone/umd/vis-network.min.js -o graphify-out/vis-network.min.js
fi
sed -i 's#https://unpkg.com/vis-network@[0-9.]*/standalone/umd/vis-network.min.js#vis-network.min.js#' graphify-out/graph.html
echo "✅ graphify-out/graph.html regenerated (offline-ready)"
