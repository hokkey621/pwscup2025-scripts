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


K_TARGET = 15


def get_column_specs() -> dict[str, dict[str, object]]:
    """Ci/Bi 列仕様を返すヘルパー。"""

    return CiDataFrame.COL_SPECS


def seed_everything(seed: int | None) -> None:
    """乱数シードをまとめて固定。"""
    if seed is None:
        return
    random.seed(seed)
    np.random.seed(seed)


def build_k_anonymous_groups(num_rows: int, k: int) -> list[list[int]]:
    """シャッフルした行番号から k 以上のグループを構成する。"""

    if num_rows < k:
        raise ValueError(f"k={k} に対して行数 {num_rows} が不足しています")

    order = np.random.permutation(num_rows)
    groups: list[list[int]] = []
    start = 0
    while start < num_rows:
        end = min(start + k, num_rows)
        current = order[start:end].tolist()
        if len(current) < k and groups:
            groups[-1].extend(current)
        else:
            groups.append(current)
        start = end
    return groups


def _choose_mode(values: pd.Series) -> str | int | float:
    mode_vals = values.mode(dropna=False)
    if mode_vals.empty:
        return ""
    # tie-breaker: lexical order after casting to string
    mode_list = sorted(mode_vals.astype(str).tolist())
    winner = mode_list[0]
    # try to keep numeric types as numeric if possible
    if winner.isdigit():
        try:
            return int(winner)
        except ValueError:
            return winner
    try:
        return float(winner)
    except ValueError:
        return winner


def _aggregate_numeric(values: pd.Series, spec: dict[str, object]) -> float | int:
    series = pd.to_numeric(values, errors="coerce")
    if series.notna().any():
        agg_val = float(series.mean())
    else:
        agg_val = float(spec["min"])
    min_val = float(spec["min"])
    max_val = float(spec["max"])
    agg_val = min(max(agg_val, min_val), max_val)
    places = spec.get("max_decimal_places")
    if places is not None:
        agg_val = round(agg_val, int(places))
        if int(places) == 0:
            return int(agg_val)
    return agg_val


def _aggregate_date(values: pd.Series, spec: dict[str, object]) -> str:
    series = pd.to_datetime(values, errors="coerce")
    series = series.dropna()
    if series.empty:
        candidate = pd.to_datetime(spec["min"])
    else:
        candidate = series.sort_values().iloc[len(series) // 2]
    min_dt = pd.to_datetime(spec["min"])
    max_dt = pd.to_datetime(spec["max"])
    candidate = min(max(candidate, min_dt), max_dt)
    return candidate.strftime("%Y-%m-%d")


def aggregate_group_block(block: pd.DataFrame, specs: dict[str, dict[str, object]]) -> dict[str, object]:
    aggregated: dict[str, object] = {}
    for col in block.columns:
        spec = specs.get(col, {})
        col_type = spec.get("type")
        if col_type == "category":
            aggregated[col] = _choose_mode(block[col])
        elif col_type == "date":
            aggregated[col] = _aggregate_date(block[col], spec)
        elif col_type == "number":
            aggregated[col] = _aggregate_numeric(block[col], spec)
        else:
            aggregated[col] = _choose_mode(block[col])
    return aggregated


def apply_k_anonymity(df: pd.DataFrame, k: int) -> pd.DataFrame:
    specs = get_column_specs()
    groups = build_k_anonymous_groups(len(df), k)
    df_out = df.copy()
    for block_rows in groups:
        block = df.iloc[block_rows]
        aggregated = aggregate_group_block(block, specs)
        for col, value in aggregated.items():
            df_out.iloc[block_rows, df_out.columns.get_loc(col)] = value
    min_group = min(len(g) for g in groups)
    if min_group < k:
        raise AssertionError(f"k 匿名化に失敗しました (最小グループ {min_group})")
    return df_out


def generate_ci(df_bi: pd.DataFrame) -> pd.DataFrame:
    """Bi DataFrame から Ci DataFrame を生成する本体処理。"""

    df_k = apply_k_anonymity(df_bi, K_TARGET)
    return df_k


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
