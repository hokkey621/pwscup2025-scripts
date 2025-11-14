#!/usr/bin/env bash
set -euo pipefail

# ラズパイの役割 (pi5=メイン/UI, pi4=評価専用)
ROLE="${1:-pi5}"
if [[ "$ROLE" != "pi5" && "$ROLE" != "pi4" ]]; then
  cat <<'USAGE'
使い方: ./setup_commands.sh [pi5|pi4]
  pi5 : Raspberry Pi 5 (UI/匿名化) 用のセットアップを実行
  pi4 : Raspberry Pi 4 (評価) 用のセットアップを実行
USAGE
  exit 1
fi

REPO_URL="${REPO_URL:-git@github.com:hokkey621/pwscup2025-scripts.git}"
WORKSPACE_ROOT="${WORKSPACE_ROOT:-$HOME/workspace}"
REPO_DIR="${REPO_DIR:-$WORKSPACE_ROOT/pwscup2025-scripts}"
PYTHON_VERSION="${PYTHON_VERSION:-3.12.11}"
UV_CACHE_DIR_DEFAULT="${UV_CACHE_DIR_DEFAULT:-$REPO_DIR/webapp/outputs/.uv-cache}"

timestamp() {
  date +"%Y-%m-%d %H:%M:%S"
}

log() {
  printf '\n[%s] %s\n' "$(timestamp)" "$*"
}

ensure_uv() {
  if command -v uv >/dev/null 2>&1; then
    UV_BIN="$(command -v uv)"
    return
  fi

  log "uv が見つかりません。Installer を実行します"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  UV_BIN="$HOME/.local/bin/uv"
}

prepare_workspace() {
  log "作業ディレクトリを準備 ($WORKSPACE_ROOT)"
  mkdir -p "$WORKSPACE_ROOT"
  cd "$WORKSPACE_ROOT"

  if [[ ! -d "$REPO_DIR/.git" ]]; then
    log "リポジトリをクローン: $REPO_URL"
    git clone "$REPO_URL" "$REPO_DIR"
  else
    log "既存リポジトリを使用: $REPO_DIR"
  fi

  cd "$REPO_DIR"
  git pull --ff-only || log "git pull に失敗しました（オフラインの場合はスキップ済み）"
}

run_common_setup() {
  log "APT パッケージを更新"
  sudo apt update
  sudo apt upgrade -y
  sudo apt install -y git curl build-essential pkg-config python3-dev python3-venv

  ensure_uv

  log "Python $PYTHON_VERSION を uv でインストール"
  "$UV_BIN" python install "$PYTHON_VERSION"

  log "依存関係を同期 (uv sync)"
  mkdir -p "$UV_CACHE_DIR_DEFAULT"
  UV_CACHE_DIR="$UV_CACHE_DIR_DEFAULT" "$UV_BIN" sync
}

print_next_steps_pi5() {
  cat <<EOF
========================================
Pi5 (メイン/UI) で実行するコマンド例
----------------------------------------
# Streamlit をローカル 127.0.0.1 で起動
cd "$REPO_DIR"
UV_CACHE_DIR="$UV_CACHE_DIR_DEFAULT" \\
  uv run streamlit run webapp/app.py \\
  --server.port 8501 --server.address 127.0.0.1

# Mac からポートフォワーディングで閲覧
ssh -L 8501:127.0.0.1:8501 raspi3@<到達可能なホスト名またはIP>
# → Mac ブラウザで http://127.0.0.1:8501 を開く

# CLI デモ（匿名化→評価をワンショット）
cd "$REPO_DIR/webapp/demo_simple"
UV_CACHE_DIR="$UV_CACHE_DIR_DEFAULT" \\
  uv run python run_once.py \\
  --bi ../../data/HI_10K.csv \\
  --config config/demo.yaml \\
  --out-dir outputs/pi5_demo
========================================
EOF
}

print_next_steps_pi4() {
  cat <<EOF
========================================
Pi4 (評価専用) で実行するコマンド例
----------------------------------------
# Pi5 から匿名化結果を取得（例）
scp raspi3:/home/raspi3/workspace/pwscup2025-scripts/webapp/outputs/ci_result.csv \\
    "$REPO_DIR/webapp/outputs/ci_result.csv"

# 有用性スコアと機械学習推論を実行
cd "$REPO_DIR"
UV_CACHE_DIR="$UV_CACHE_DIR_DEFAULT" \\
  uv run python webapp/evaluate.py \\
  --bi data/HI_10K.csv \\
  --ci webapp/outputs/ci_result.csv \\
  --metrics-json webapp/outputs/metrics/ci_result.json

# 結果を Pi5 に返却（例）
scp webapp/outputs/metrics/ci_result.json \\
    raspi3:/home/raspi3/workspace/pwscup2025-scripts/webapp/outputs/metrics/
========================================
EOF
}

prepare_workspace
run_common_setup

if [[ "$ROLE" == "pi5" ]]; then
  print_next_steps_pi5
else
  print_next_steps_pi4
fi

log "セットアップ手順が完了しました"
