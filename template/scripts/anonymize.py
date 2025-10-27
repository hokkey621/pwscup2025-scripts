"""汎用的な匿名化ユーティリティ。

テンプレートをコピーした先では `CustomAnonymizer` を継承または差し替えることで
匿名化ロジックを容易に変更できる。
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
UTIL_PATH = REPO_ROOT / "util"
if str(UTIL_PATH) not in sys.path:
    sys.path.append(str(UTIL_PATH))

from pws_data_format import BiDataFrame, CiDataFrame


def seed_everything(seed: int | None) -> None:
    if seed is None:
        return
    random.seed(seed)
    np.random.seed(seed)


def load_config(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def mutate_categorical(series: pd.Series, prob: float) -> pd.Series:
    values = series.astype(str)
    unique = [v for v in sorted(set(values) - {""})]
    if len(unique) < 2:
        return values

    mask = (values != "") & (np.random.rand(len(values)) < prob)

    def pick_other(val: str) -> str:
        pool = [u for u in unique if u != val]
        return random.choice(pool) if pool else val

    values.loc[mask] = values.loc[mask].map(pick_other)
    return values


def flip_binary(series: pd.Series, prob: float) -> pd.Series:
    values = series.astype(str)
    mask = values.isin(["0", "1"]) & (np.random.rand(len(values)) < prob)
    flipped = values.copy()
    flipped.loc[mask & (values == "0")] = "1"
    flipped.loc[mask & (values == "1")] = "0"
    return flipped


def add_integer_noise(series: pd.Series, lo: int, hi: int) -> pd.Series:
    values = series.astype(str)
    blanks = values.str.strip().eq("")
    numeric = pd.to_numeric(values.where(~blanks, np.nan), errors="coerce")
    valid = numeric.dropna()
    if valid.empty:
        return values

    col_min = int(np.floor(valid.min()))
    col_max = int(np.ceil(valid.max()))
    noise = np.random.randint(lo, hi + 1, size=len(numeric))
    noisy = numeric.add(noise).clip(col_min, col_max)
    noisy = noisy.where(~blanks, np.nan)

    out = noisy.round(0).astype("float64")
    str_out = out.astype("Int64").astype(str)
    str_out[blanks] = ""
    return str_out


def add_float_noise(series: pd.Series, amplitude: float, preserve_blank: bool = True, decimals: int = 2) -> pd.Series:
    values = series.astype(str)
    blanks = values.str.strip().eq("")
    numeric = pd.to_numeric(values.where(~blanks, np.nan), errors="coerce")
    valid = numeric.dropna()
    if valid.empty:
        return values

    col_min = float(valid.min())
    col_max = float(valid.max())
    noise = np.random.uniform(-amplitude, amplitude, size=len(numeric))
    noisy = numeric.add(noise).clip(col_min, col_max)
    if preserve_blank:
        noisy = noisy.where(~blanks, np.nan)
    else:
        fill = np.random.uniform(col_min, col_max, size=len(numeric))
        noisy = noisy.where(~blanks, fill)

    noisy = noisy.round(decimals)
    str_out = noisy.astype(str)
    if preserve_blank:
        str_out[blanks] = ""
    return str_out


def add_age_noise(series: pd.Series, cfg: Dict[str, int]) -> pd.Series:
    values = series.astype(str)
    blanks = values.str.strip().eq("")
    numeric = pd.to_numeric(values.where(~blanks, np.nan), errors="coerce")
    valid = numeric.dropna()
    if valid.empty:
        return values

    lo = int(cfg.get("lo", -2))
    hi = int(cfg.get("hi", 2))
    min_age = int(cfg.get("min_age", 2))
    max_age = int(cfg.get("max_age", 110))
    noise = np.random.randint(lo, hi + 1, size=len(numeric))
    noisy = numeric.add(noise).clip(min_age, max_age)
    noisy = noisy.where(~blanks, np.nan)
    out = noisy.round(0).astype("float64")
    str_out = out.astype("Int64").astype(str)
    str_out[blanks] = ""
    return str_out


def read_bi_dataframe(path: Path) -> pd.DataFrame:
    try:
        return BiDataFrame.read_csv(str(path))
    except ExceptionGroup as eg:
        print("[WARN] BiDataFrame validation failed, fallback to pandas.read_csv", file=sys.stderr)
        for sub in eg.exceptions:
            print(f"  - {sub}", file=sys.stderr)
        df = pd.read_csv(path)
        if "AGE" in df.columns:
            df["AGE"] = pd.to_numeric(df["AGE"], errors="coerce").clip(lower=2, upper=110)
        return df


class TemplateAnonymizer:
    def __init__(self, params: Dict):
        self.params = params

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        for col, prob in self.params.get("categorical_swap_prob", {}).items():
            if col in df.columns:
                df[col] = mutate_categorical(df[col], prob)

        for col, prob in self.params.get("flag_flip_prob", {}).items():
            if col in df.columns:
                df[col] = flip_binary(df[col], prob)

        age_cfg = self.params.get("age_noise")
        if age_cfg and "AGE" in df.columns:
            df["AGE"] = add_age_noise(df["AGE"], age_cfg)

        for col, bounds in self.params.get("int_noise", {}).items():
            if col in df.columns:
                lo, hi = bounds
                df[col] = add_integer_noise(df[col], int(lo), int(hi))

        for col, amp in self.params.get("float_noise", {}).items():
            if col in df.columns:
                df[col] = add_float_noise(df[col], float(amp), preserve_blank=True)

        for col, amp in self.params.get("float_noise_with_blanks", {}).items():
            if col in df.columns:
                df[col] = add_float_noise(df[col], float(amp), preserve_blank=False)

        return df


def run_anonymization(bi_path: Path, ci_path: Path, params: Dict) -> None:
    df_bi = read_bi_dataframe(bi_path)
    anonymizer = TemplateAnonymizer(params)
    df_ci = anonymizer.transform(df_bi)
    CiDataFrame(df_ci).to_csv(str(ci_path))


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="テンプレート匿名化器")
    parser.add_argument("bi", help="Bi.csv のパス")
    parser.add_argument("ci", help="出力 Ci.csv のパス")
    parser.add_argument("--config", default="config/params.json", help="JSON 設定ファイル")
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    seed_everything(args.seed)
    params = load_config(Path(args.config))
    run_anonymization(Path(args.bi), Path(args.ci), params)


if __name__ == "__main__":
    main()
