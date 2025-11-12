#!/usr/bin/env python3
"""差分プライバシーベースの Bi→Ci 変換スクリプト。"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, List

import numpy as np
import pandas as pd
from diffprivlib.mechanisms import LaplaceBoundedDomain


def locate_repo_root() -> Path:
    """`util` ディレクトリが見つかる親をルートとみなす。"""
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


CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "params.json"
COLUMN_RANGE_PATH = REPO_ROOT / "data" / "columns_range.json"

CATEGORICAL_COLS = ["GENDER", "RACE", "ETHNICITY"]
FLAG_COLS = ["asthma_flag", "stroke_flag", "obesity_flag", "depression_flag"]
INTEGER_COLS = [
    "AGE",
    "encounter_count",
    "num_procedures",
    "num_medications",
    "num_immunizations",
    "num_allergies",
    "num_devices",
]
FLOAT_COLS = [
    "mean_systolic_bp",
    "mean_diastolic_bp",
    "mean_bmi",
    "mean_weight",
]


def seed_everything(seed: int | None) -> None:
    if seed is None:
        return
    random.seed(seed)
    np.random.seed(seed)


@lru_cache(maxsize=1)
def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"config が見つかりません: {CONFIG_PATH}")
    with CONFIG_PATH.open("r", encoding="utf-8") as fp:
        return json.load(fp)


@lru_cache(maxsize=1)
def load_column_ranges() -> dict[str, Any]:
    with COLUMN_RANGE_PATH.open("r", encoding="utf-8") as fp:
        data = json.load(fp)
    return data.get("columns", {})


def get_column_meta(column: str) -> dict[str, Any]:
    return load_column_ranges().get(column, {})


def ensure_bounds(column: str) -> tuple[float, float]:
    meta = get_column_meta(column)
    if "min" not in meta or "max" not in meta:
        raise ValueError(f"{column} に min/max が未定義のためラプラス機構を適用できません")
    return float(meta["min"]), float(meta["max"])


def laplace_mechanism(value: float, column: str, epsilon: float) -> float:
    if epsilon <= 0:
        return value
    lower, upper = ensure_bounds(column)
    sensitivity = max(upper - lower, 1e-6)
    mech = LaplaceBoundedDomain(
        epsilon=epsilon,
        sensitivity=sensitivity,
        lower=lower,
        upper=upper,
    )
    return float(mech.randomise(value))


def apply_dp_numeric(series: pd.Series, column: str, epsilon: float, *, round_int: bool) -> pd.Series:
    if epsilon <= 0 or series.empty:
        return series
    numeric = pd.to_numeric(series, errors="coerce").astype(float)
    mask = numeric.notna()
    if not mask.any():
        return series
    sanitized = numeric.copy()
    for idx in numeric.index[mask]:
        sanitized_value = laplace_mechanism(float(numeric.at[idx]), column, epsilon)
        sanitized.at[idx] = sanitized_value
    meta = get_column_meta(column)
    lower = meta.get("min")
    upper = meta.get("max")
    if lower is not None or upper is not None:
        sanitized = sanitized.clip(lower=lower, upper=upper)
    if round_int:
        sanitized = sanitized.round().astype("Int64")
    else:
        decimals = meta.get("max_decimal_places", 2)
        sanitized = sanitized.round(decimals)
    return sanitized


def randomized_response(series: pd.Series, epsilon: float, allowed_values: Iterable[str]) -> pd.Series:
    if epsilon <= 0 or series.empty:
        return series
    allowed = [str(v) for v in allowed_values if str(v).strip()]
    if len(allowed) < 2:
        allowed = sorted({str(v) for v in series.dropna().unique() if str(v).strip()})
    if len(allowed) < 2:
        return series

    k = len(allowed)
    keep_prob = math.exp(epsilon) / (math.exp(epsilon) + k - 1)
    rng = np.random.default_rng()
    values = series.astype("object").copy()
    mask = values.notna()
    candidates = np.array(allowed)
    for idx in values.index[mask]:
        if rng.random() <= keep_prob:
            continue
        # サンプリング時は現在値を除外
        pool = candidates[candidates != str(values.at[idx])]
        if pool.size == 0:
            continue
        values.at[idx] = rng.choice(pool)
    return values


def get_allowed_values(column: str) -> List[str]:
    meta = get_column_meta(column)
    values = meta.get("values")
    if not values:
        return []
    return [str(v) for v in values if v not in (None, "")]


def generate_ci(df_bi: pd.DataFrame) -> pd.DataFrame:
    cfg = load_config()
    label = cfg.get("label", "dp_experiment")
    eps_numeric = float(cfg.get("epsilon_numeric", cfg.get("epsilon", 1.0)))
    eps_float = float(cfg.get("epsilon_float", eps_numeric))
    eps_age = float(cfg.get("epsilon_age", eps_numeric))
    eps_categorical = float(cfg.get("epsilon_categorical", cfg.get("epsilon", 1.0)))
    eps_flags = float(cfg.get("epsilon_flags", eps_categorical))

    df = df_bi.copy()

    # カテゴリ列をランダム化応答で保護
    for col in CATEGORICAL_COLS:
        if col not in df.columns:
            continue
        allowed = get_allowed_values(col)
        df[col] = randomized_response(df[col], eps_categorical, allowed)

    # フラグ列（2値）は同じロジックで処理
    for col in FLAG_COLS:
        if col not in df.columns:
            continue
        randomized = randomized_response(df[col], eps_flags, ["0", "1"])
        numeric_flags = pd.to_numeric(randomized, errors="coerce")
        df[col] = numeric_flags.round().clip(0, 1).astype("Int64")

    for col in INTEGER_COLS:
        if col not in df.columns:
            continue
        epsilon = eps_age if col == "AGE" else eps_numeric
        df[col] = apply_dp_numeric(df[col], col, epsilon, round_int=True)

    for col in FLOAT_COLS:
        if col not in df.columns:
            continue
        df[col] = apply_dp_numeric(df[col], col, eps_float, round_int=False)

    df.attrs["dp_label"] = label
    return df


def run_anonymization(bi_path: Path, ci_path: Path, seed: int | None = None) -> None:
    seed_everything(seed)
    df_bi = pd.read_csv(bi_path)
    df_ci = generate_ci(df_bi)
    ci_path.parent.mkdir(parents=True, exist_ok=True)
    CiDataFrame(df_ci).to_csv(str(ci_path))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="差分プライバシー版 Bi → Ci 変換")
    parser.add_argument("bi", help="入力となる Bi.csv")
    parser.add_argument("ci", help="出力する Ci.csv")
    parser.add_argument("--seed", type=int, default=42, help="乱数シード（任意）")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_anonymization(Path(args.bi), Path(args.ci), seed=args.seed)


if __name__ == "__main__":
    main()
