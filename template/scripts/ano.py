#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""テンプレート用匿名化スクリプト。

`generate_ci` を編集して、Bi → Ci の加工ロジックを記述してください。
`run_experiment.py` からはこのモジュールの `run_anonymization` が呼ばれます。
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd


def locate_repo_root() -> Path:
    """util ディレクトリが見つかる親ディレクトリをリポジトリルートとみなす。"""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "util").is_dir():
            return parent
    return here.parents[-1]


REPO_ROOT = locate_repo_root()
UTIL_DIR = REPO_ROOT / "util"
if str(UTIL_DIR) not in sys.path:
    sys.path.append(str(UTIL_DIR))

from pws_data_format import CiDataFrame  # noqa: E402


def seed_everything(seed: int | None) -> None:
    """乱数シードをまとめて固定。"""
    if seed is None:
        return
    random.seed(seed)
    np.random.seed(seed)


def generate_ci(df_bi: pd.DataFrame) -> pd.DataFrame:
    """Bi DataFrame から Ci DataFrame を生成する本体処理。

    デフォルトではそのままコピーして返すだけなので、必ず編集してください。
    返り値は `CiDataFrame` で書き出せる pandas.DataFrame を期待します。
    """
    # TODO: ここを書き換えて独自の匿名化ロジックを実装してください。
    return df_bi.copy()


def run_anonymization(bi_path: Path, ci_path: Path, seed: int | None = None) -> None:
    """Bi を読み込み、Ci を生成して保存するラッパー関数。"""
    seed_everything(seed)
    df_bi = pd.read_csv(bi_path)
    df_ci = generate_ci(df_bi)
    ci_path.parent.mkdir(parents=True, exist_ok=True)
    CiDataFrame(df_ci).to_csv(str(ci_path))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bi → Ci 変換テンプレート")
    parser.add_argument("bi", help="入力となる Bi.csv")
    parser.add_argument("ci", help="出力する Ci.csv")
    parser.add_argument("--seed", type=int, default=42, help="乱数シード（任意）")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_anonymization(Path(args.bi), Path(args.ci), seed=args.seed)


if __name__ == "__main__":
    main()
