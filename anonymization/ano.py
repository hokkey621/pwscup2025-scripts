#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys, os
import argparse
import random
from typing import List

import numpy as np
import pandas as pd

# モジュールの相対参照制限を強制的に回避
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, '..', 'util'))
from pws_data_format import BiDataFrame, CiDataFrame

def mutate_categorical(series: pd.Series, p: float) -> pd.Series:
    """非空セルのみ、確率 p で列内の“別の値”に置き換え。"""
    s = series.astype(str)
    uniq = [v for v in sorted(set(s) - {""})]
    if len(uniq) < 2:
        return s  # 置換不能
    mask = (s != "") & (np.random.rand(len(s)) < p)

    def pick_other(val: str) -> str:
        choices = [u for u in uniq if u != val]
        return random.choice(choices) if choices else val

    s.loc[mask] = s.loc[mask].map(pick_other)
    return s


def process_int_column(df: pd.DataFrame, col: str, lo: int, hi: int, 
                      min_val: int = None, max_val: int = None) -> None:
    """整数列：空欄個数を記録→非空に乱数加算＆クランプ→空欄は範囲で埋め→
       最後に元の空欄個数ぶんをランダムに空欄化。"""
    if col not in df.columns:
        return
    s_raw = df[col].astype(str)
    is_blank = s_raw.str.strip().eq("")
    blanks_n = int(is_blank.sum())

    s_num = pd.to_numeric(s_raw.where(~is_blank, np.nan), errors="coerce")
    non_na = s_num.dropna()
    if non_na.empty:
        df[col] = s_raw
        return

    # 指定されたmin/max値を使用、なければデータから算出
    if min_val is not None and max_val is not None:
        vmin = min_val
        vmax = max_val
    else:
        vmin = int(np.floor(non_na.min()))
        vmax = int(np.ceil(non_na.max()))

    delta = np.random.randint(lo, hi + 1, size=len(s_num))
    s_num = s_num.add(delta).clip(lower=vmin, upper=vmax)

    fill_vals = np.random.randint(vmin, vmax + 1, size=len(s_num))
    s_num = s_num.where(~is_blank, fill_vals)

    out = s_num.round(0).astype(int).astype(str)

    if blanks_n > 0:
        idx = np.random.choice(len(out), size=blanks_n, replace=False)
        out.iloc[idx] = ""
    df[col] = out


def process_float_add(df: pd.DataFrame, col: str, lo: float, hi: float, 
                     decimals: int = 2, min_val: float = None, max_val: float = None) -> None:
    """浮動小数点列：非空のみ乱数加算＆クランプ。空欄はそのまま。"""
    if col not in df.columns:
        return
    s_raw = df[col].astype(str)
    is_blank = s_raw.str.strip().eq("")
    s_num = pd.to_numeric(s_raw.where(~is_blank, np.nan), errors="coerce")
    non_na = s_num.dropna()
    if non_na.empty:
        return

    # 指定されたmin/max値を使用、なければデータから算出
    if min_val is not None and max_val is not None:
        vmin = min_val
        vmax = max_val
    else:
        vmin = float(non_na.min())
        vmax = float(non_na.max())
    delta = np.random.uniform(lo, hi, size=len(s_num))
    s_num = s_num.add(delta).clip(lower=vmin, upper=vmax).round(decimals)

    df[col] = s_num.where(~is_blank, "").astype(object)


def process_float_with_blanks(df: pd.DataFrame, col: str, lo: float, hi: float, 
                             decimals: int = 2, min_val: float = None, max_val: float = None) -> None:
    """浮動小数点列：空欄個数を保存→非空にノイズ→クランプ→空欄は[min,max]で埋め→
       最後に元の空欄個数ぶんランダムに空欄化。"""
    if col not in df.columns:
        return
    s_raw = df[col].astype(str)
    is_blank = s_raw.str.strip().eq("")
    blanks_n = int(is_blank.sum())

    s_num = pd.to_numeric(s_raw.where(~is_blank, np.nan), errors="coerce")
    non_na = s_num.dropna()
    if non_na.empty:
        return

    # 指定されたmin/max値を使用、なければデータから算出
    if min_val is not None and max_val is not None:
        vmin = min_val
        vmax = max_val
    else:
        vmin = float(non_na.min())
        vmax = float(non_na.max())
    delta = np.random.uniform(lo, hi, size=len(s_num))
    s_num = s_num.add(delta).clip(lower=vmin, upper=vmax)

    fill_vals = np.random.uniform(vmin, vmax, size=len(s_num))
    s_num = s_num.where(~is_blank, fill_vals).round(decimals)

    out = s_num.astype(str)
    if blanks_n > 0:
        idx = np.random.choice(len(out), size=blanks_n, replace=False)
        out.iloc[idx] = ""
    df[col] = out


def flip_flag_with_prob(df: pd.DataFrame, col: str, p: float) -> None:
    """0/1フラグを確率 p で反転。非空・0/1のみ対象。"""
    if col not in df.columns:
        return
    s_raw = df[col].astype(str)
    is_zero = s_raw == "0"
    is_one = s_raw == "1"
    mask = (is_zero | is_one) & (np.random.rand(len(s_raw)) < p)

    flipped = s_raw.copy()
    flipped.loc[mask & is_zero] = "1"
    flipped.loc[mask & is_one] = "0"
    df[col] = flipped


def process_age_add(df: pd.DataFrame, col: str = "AGE",
                    lo: int = -2, hi: int = 2,
                    min_age: int = 2, max_age: int = 110) -> None:
    """AGE列：非空のみ整数ノイズ（[lo,hi]）を加算し、[min_age,max_age]でクランプ。
       空欄はそのまま。"""
    if col not in df.columns:
        return
    s_raw = df[col].astype(str)
    is_blank = s_raw.str.strip().eq("")
    s_num = pd.to_numeric(s_raw.where(~is_blank, np.nan), errors="coerce")
    non_na = s_num.dropna()
    if non_na.empty:
        return

    delta = np.random.randint(lo, hi + 1, size=len(s_num))
    s_num = s_num.add(delta).clip(lower=min_age, upper=max_age).round(0)

    # 出力は他列と同様に文字列
    df[col] = s_num.where(~is_blank, "").astype(object).astype(str)


def main():
    parser = argparse.ArgumentParser(description="匿名化します（BIRTHDATE等の日付処理なし）。")
    parser.add_argument("input_csv")
    parser.add_argument("output_csv")
    parser.add_argument("--seed", type=int, default=None, help="乱数シード（再現用、省略可）")
    args = parser.parse_args()

    if args.seed is not None:
        np.random.seed(args.seed)
        random.seed(args.seed)

    # Biを読み込み
    df = BiDataFrame.read_csv(args.input_csv)

    # ---- カテゴリ列のランダム置換 ----
    if "GENDER" in df.columns:
        df["GENDER"] = mutate_categorical(df["GENDER"], p=0.11)
    if "RACE" in df.columns:
        df["RACE"] = mutate_categorical(df["RACE"], p=0.12)
    if "ETHNICITY" in df.columns:
        df["ETHNICITY"] = mutate_categorical(df["ETHNICITY"], p=0.13)

    # ---- AGE（整数ノイズ; 空欄はそのまま）----
    process_age_add(df, col="AGE", lo=-2, hi=2, min_age=2, max_age=110)

    # ---- 整数ノイズ付加 (columns_range.jsonの値域に従う) ----
    process_int_column(df, "encounter_count",   lo=-10, hi=10, min_val=4,    max_val=1211)
    process_int_column(df, "num_procedures",    lo=-10, hi=10, min_val=0,    max_val=2442)
    process_int_column(df, "num_medications",   lo=-5,  hi=5,  min_val=0,    max_val=7195)
    process_int_column(df, "num_immunizations", lo=-3,  hi=3,  min_val=0,    max_val=40)
    process_int_column(df, "num_allergies",     lo=-2,  hi=2,  min_val=0,    max_val=17)
    process_int_column(df, "num_devices",       lo=-5,  hi=5,  min_val=0,    max_val=160)

    # ---- *_flag は確率で反転 ----
    flip_flag_with_prob(df, "asthma_flag",     p=0.14)
    flip_flag_with_prob(df, "stroke_flag",     p=0.15)
    flip_flag_with_prob(df, "obesity_flag",    p=0.16)
    flip_flag_with_prob(df, "depression_flag", p=0.17)

    # ---- 実数ノイズ付加 (columns_range.jsonの値域に従う) ----
    process_float_add(df, "mean_systolic_bp",   lo=-10.0, hi=10.0, decimals=2, min_val=37.22,  max_val=172.85)
    process_float_add(df, "mean_diastolic_bp",  lo=-8.0,  hi=8.0,  decimals=2, min_val=1.78,   max_val=126.17)
    process_float_add(df, "mean_weight",        lo=-3.0,  hi=3.0,  decimals=2, min_val=4.55,   max_val=196.7)

    # ---- 実数ノイズ付加（空欄処理込み) ----
    process_float_with_blanks(df, "mean_bmi",   lo=-6.0,  hi=6.0,  decimals=2, min_val=2.97,   max_val=73.58)

    # ---- 出力 ----
    Ci_df = CiDataFrame(df)
    Ci_df.to_csv(args.output_csv)


if __name__ == "__main__":
    main()
