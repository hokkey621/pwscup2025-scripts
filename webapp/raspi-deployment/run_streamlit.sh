#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
UV_BIN="${UV_BIN:-uv}"
PORT="${PORT:-8501}"
ADDRESS="${ADDRESS:-127.0.0.1}"
UV_CACHE_DIR="${UV_CACHE_DIR:-$REPO_ROOT/outputs/.uv-cache}"

mkdir -p "$UV_CACHE_DIR"
cd "$REPO_ROOT"

echo "[info] Streamlit を ${ADDRESS}:${PORT} で起動します"
echo "[info] UV_CACHE_DIR=$UV_CACHE_DIR"

UV_CACHE_DIR="$UV_CACHE_DIR" \
  "$UV_BIN" run streamlit run app.py \
  --server.port "$PORT" --server.address "$ADDRESS"
