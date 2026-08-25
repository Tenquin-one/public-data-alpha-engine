#!/bin/sh
set -eu
PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
export PYTHONPATH="$PROJECT_DIR/src"
python3 -m public_data_alpha_engine.cli --db "$PROJECT_DIR/data/alpha_engine.sqlite" collect-seoul
