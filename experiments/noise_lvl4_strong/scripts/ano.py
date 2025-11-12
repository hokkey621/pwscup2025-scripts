#!/usr/bin/env python3
"""ノイズ量を設定可能な Bi→Ci 変換スクリプト。"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import numpy as np
import pandas as pd


def locate_repo_root() -> Path:
    """`util` ディレクトリが見つかる親をリポジトリルートとみなす。"""
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
INT_NOISE_BASE = {
    "encounter_count": 4,
    "num_procedures": 12,
    "num_medications": 8,
    "num_immunizations": 3,
    "num_allergies": 2,
    "num_devices": 1,
}
FLOAT_NOISE_BASE = {
    "mean_systolic_bp": 2.0,
    "mean_diastolic_bp": 1.5,
    "mean_bmi": 0.4,
    "mean_weight": 4.0,
}

_CONFIG_CACHE: Optional[Dict[str, Any]] = None
_COLUMN_RANGE_CACHE: Optional[Dict[str, Any]] = None


def seed_everything(seed: int | None) -> None:
    if seed is None:
        return
    random.seed(seed)
    np.random.seed(seed)


def load_config() -> Dict[str, Any]:
    global _CONFIG_CACHE
    if _CONFIG_CACHE is None:
        if not CONFIG_PATH.exists():
            raise FileNotFoundError(f"config が見つかりません: {CONFIG_PATH}")
        with CONFIG_PATH.open("r", encoding="utf-8") as fp:
            _CONFIG_CACHE = json.load(fp)
    return _CONFIG_CACHE


def load_column_ranges() -> Dict[str, Any]:
    global _COLUMN_RANGE_CACHE
    if _COLUMN_RANGE_CACHE is None:
        with COLUMN_RANGE_PATH.open("r", encoding="utf-8") as fp:
            data = json.load(fp)
        _COLUMN_RANGE_CACHE = data.get("columns", {})
    return _COLUMN_RANGE_CACHE


def get_allowed_values(column: str) -> List[str]:
    meta = load_column_ranges().get(column, {})
    values = meta.get("values") or []
    return [str(v) for v in values if v not in (None, "")]


def clip_numeric_series(series: pd.Series, column: str) -> pd.Series:
    meta = load_column_ranges().get(column, {})
    if meta.get("type") != "number":
        return series
    lower = meta.get("min")
    upper = meta.get("max")
    if lower is not None or upper is not None:
        series = series.clip(lower=lower, upper=upper)
    return series


def mutate_categorical(series: pd.Series, prob: float, allowed: Iterable[str]) -> pd.Series:
    if prob <= 0:
        return series
    allowed_list = [val for val in allowed if val not in (None, "")]
    if len(allowed_list) < 2:
        unique = sorted({str(v) for v in series.dropna().unique() if str(v).strip()})
        allowed_list = unique
    if len(allowed_list) < 2:
        return series

    values = series.astype("object").copy()
    valid_mask = values.notna()
    swap_mask = valid_mask & (np.random.rand(len(values)) < prob)
    if not swap_mask.any():
        return series

    for idx in values.index[swap_mask]:
        current = values.at[idx]
        pool = [v for v in allowed_list if v != current]
        if pool:
            values.at[idx] = random.choice(pool)
    return values


def flip_binary(series: pd.Series, prob: float) -> pd.Series:
    if prob <= 0 or series.empty:
        return series
    mask = series.isin([0, 1])
    flip_mask = mask & (np.random.rand(len(series)) < prob)
    if not flip_mask.any():
        return series
    result = series.copy()
    result.loc[flip_mask & (series == 0)] = 1
    result.loc[flip_mask & (series == 1)] = 0
    return result


def compute_span(base: float, scale: float) -> int:
    if scale <= 0 or base <= 0:
        return 0
    return max(1, int(math.ceil(base * scale)))


def apply_integer_noise(series: pd.Series, span: int, column: str) -> pd.Series:
    if span <= 0:
        return series
    numeric = pd.to_numeric(series, errors="coerce")
    mask = numeric.notna()
    if not mask.any():
        return series
    idx = mask.index[mask]
    noise = np.random.randint(-span, span + 1, size=len(idx))
    numeric.loc[idx] = numeric.loc[idx] + noise
    numeric = clip_numeric_series(numeric, column)
    numeric.loc[idx] = numeric.loc[idx].round()
    result = series.copy()
    result.loc[idx] = numeric.loc[idx].astype(int)
    return result


def apply_float_noise(series: pd.Series, amplitude: float, column: str) -> pd.Series:
    if amplitude <= 0:
        return series
    numeric = pd.to_numeric(series, errors="coerce")
    mask = numeric.notna()
    if not mask.any():
        return series
    idx = mask.index[mask]
    noise = np.random.normal(0.0, amplitude, size=len(idx))
    numeric.loc[idx] = numeric.loc[idx] + noise
    numeric = clip_numeric_series(numeric, column)
    decimals = load_column_ranges().get(column, {}).get("max_decimal_places", 2)
    numeric.loc[idx] = numeric.loc[idx].round(decimals)
    result = series.copy()
    result.loc[idx] = numeric.loc[idx]
    return result


def generate_ci(df_bi: pd.DataFrame) -> pd.DataFrame:
    cfg = load_config()
    df = df_bi.copy()

    cat_prob = float(cfg.get("categorical_swap_prob", 0.0))
    for col in CATEGORICAL_COLS:
        if col in df.columns:
            allowed = get_allowed_values(col)
            df[col] = mutate_categorical(df[col], cat_prob, allowed)

    flag_prob = float(cfg.get("flag_flip_prob", 0.0))
    for col in FLAG_COLS:
        if col in df.columns:
            df[col] = flip_binary(df[col], flag_prob)

    age_span = int(cfg.get("age_noise_span", 0))
    if age_span > 0 and "AGE" in df.columns:
        df["AGE"] = apply_integer_noise(df["AGE"], age_span, "AGE")

    int_scale = float(cfg.get("int_noise_scale", 0.0))
    if int_scale > 0:
        for col, base_span in INT_NOISE_BASE.items():
            if col not in df.columns:
                continue
            span = compute_span(base_span, int_scale)
            if span > 0:
                df[col] = apply_integer_noise(df[col], span, col)

    float_scale = float(cfg.get("float_noise_scale", 0.0))
    if float_scale > 0:
        for col, base_amp in FLOAT_NOISE_BASE.items():
            if col not in df.columns:
                continue
            amplitude = base_amp * float_scale
            if amplitude > 0:
                df[col] = apply_float_noise(df[col], amplitude, col)

    return df


def run_anonymization(bi_path: Path, ci_path: Path, seed: int | None = None) -> None:
    seed_everything(seed)
    df_bi = pd.read_csv(bi_path)
    df_ci = generate_ci(df_bi)
    ci_path.parent.mkdir(parents=True, exist_ok=True)
    CiDataFrame(df_ci).to_csv(str(ci_path))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bi → Ci 変換（ノイズ量調整版）")
    parser.add_argument("bi", help="入力となる Bi.csv")
    parser.add_argument("ci", help="出力する Ci.csv")
    parser.add_argument("--seed", type=int, default=42, help="乱数シード（任意）")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_anonymization(Path(args.bi), Path(args.ci), seed=args.seed)


if __name__ == "__main__":
    main()
