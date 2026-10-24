#!/usr/bin/env bash
# Complete acceptance test runner for RIPPLE
set -e

echo "=========================================================="
echo "🌊 Running RIPPLE Complete Acceptance Test Suite (Phases 1-6)"
echo "=========================================================="

python -m pytest tests/test_diffmap.py -v
python -m pytest tests/test_impact.py -v
python -m pytest tests/test_triage.py -v
python -m pytest tests/test_eval_harness.py -v
python -m pytest tests/test_cli_e2e.py -v
python -m pytest tests/test_ripplemap.py -v
python -m pytest tests/test_draft.py -v

echo ""
echo "=========================================================="
echo "🎉 ALL 38 ACCEPTANCE TESTS PASSED! RIPPLE IS READY!"
echo "=========================================================="
