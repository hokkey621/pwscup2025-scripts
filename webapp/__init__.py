"""Streamlitデモ用webappパッケージの初期化モジュール。"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"

DEFAULT_BI_PATH = DATA_DIR / "HI_10K.csv"
DEFAULT_AI_PATH = DATA_DIR / "HI_100K.csv"
DEFAULT_ANS_PATH = DATA_DIR / "HI_ans.csv"

APP_TITLE = "SecHack365 医療AI匿名化デモ"
APP_DESCRIPTION = (
    "医療データBiを匿名化し、PWS CUP 2025評価指標を即時で可視化するMVPです。"
)

