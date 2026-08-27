#!/bin/sh
set -eu
PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
OUTPUT_DIR=${1:?usage: run_airport_friction.sh /path/to/data-branch-checkout}
export PYTHONPATH="$PROJECT_DIR/src"
python3 -m public_data_alpha_engine.cli collect-airport \
  --output "$OUTPUT_DIR" \
  --trigger-source local \
  --strict
