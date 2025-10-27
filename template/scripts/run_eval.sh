#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "Usage: $0 <Bi.csv> <Ci.csv> [extra eval_all options...]" >&2
  exit 1
fi

uv run python evaluation/eval_all.py "$@"
