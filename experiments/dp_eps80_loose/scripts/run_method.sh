#!/usr/bin/env bash
set -euo pipefail

# 手法ディレクトリを引数に取り、テンプレの run_experiment.py を定形パラメータで実行します。
# Bi→Ci 生成だけでなく、Di 学習と攻撃評価までまとめて走らせます。
#
# 例:
#   template/scripts/run_method.sh experiments/my_method --print-details --skip-check

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <method_dir> [extra run_experiment.py options...]" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

METHOD_DIR="$1"
shift || true

if [ ! -d "$METHOD_DIR" ]; then
  echo "Error: method directory not found: $METHOD_DIR" >&2
  exit 1
fi

METHOD_NAME="$(basename "$METHOD_DIR")"
RUN_SCRIPT="$METHOD_DIR/scripts/run_experiment.py"

if [ ! -f "$RUN_SCRIPT" ]; then
  echo "Error: run_experiment.py not found at $RUN_SCRIPT" >&2
  exit 1
fi

CI_PATH="$METHOD_DIR/outputs/ci/${METHOD_NAME}.csv"
METRICS_PATH="$METHOD_DIR/reports/metrics.json"

PYTHONPATH="${PYTHONPATH:-}:$REPO_ROOT/util" uv run python "$RUN_SCRIPT" \
  --bi "$REPO_ROOT/data/HI_10K.csv" \
  --ci "$CI_PATH" \
  --metrics-json "$METRICS_PATH" \
  --print-details \
  "$@"
