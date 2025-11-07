"""匿名化処理およびフォーム入力整形ロジック。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd
from pandas.api import types as pdt

from . import DEFAULT_BI_PATH


ALGORITHM_OPTIONS: list[tuple[str, str]] = [
    ("naive", "アルゴリズムA: ナイーブ加工 (そのままコピー)"),
    ("main", "アルゴリズムB: 本命加工 (ノイズ付与)"),
]
ALGORITHM_LABELS: Dict[str, str] = dict(ALGORITHM_OPTIONS)


class AnonymizationError(Exception):
    """匿名化処理で発生した例外。"""


@dataclass(frozen=True)
class ColumnProfile:
    """フォーム生成およびサニタイズ用の列プロファイル。"""

    name: str
    kind: str  # "int" | "float" | "category"
    default: Any
    min_value: float | None = None
    max_value: float | None = None
    examples: tuple[str, ...] = ()


@dataclass
class AnonymizationResult:
    """匿名化ボタン押下後の結果。"""

    bi_prime: pd.DataFrame
    ci: pd.DataFrame
    new_index: int
    entry: dict[str, Any]


def load_base_bi(path: str | Path = DEFAULT_BI_PATH) -> pd.DataFrame:
    """Biの参照CSVを読み込む。"""

    df = pd.read_csv(path)
    df.columns = df.columns.str.strip()
    return df


def build_column_profiles(df: pd.DataFrame) -> dict[str, ColumnProfile]:
    """列の型情報とフォーム初期値をまとめる。"""

    profiles: dict[str, ColumnProfile] = {}
    for col in df.columns:
        series = df[col]
        if pdt.is_integer_dtype(series):
            default = int(series.median())
            profiles[col] = ColumnProfile(
                name=col,
                kind="int",
                default=default,
                min_value=float(series.min()),
                max_value=float(series.max()),
            )
        elif pdt.is_float_dtype(series):
            default = float(series.median())
            profiles[col] = ColumnProfile(
                name=col,
                kind="float",
                default=default,
                min_value=float(series.min()),
                max_value=float(series.max()),
            )
        else:
            # object列は代表値とユニーク値サンプルを保持
            candidates = series.dropna().astype(str).unique().tolist()
            default = candidates[0] if candidates else ""
            examples = tuple(candidates[:5])
            profiles[col] = ColumnProfile(
                name=col,
                kind="category",
                default=default,
                examples=examples,
            )
    return profiles


def default_form_values(profiles: dict[str, ColumnProfile]) -> dict[str, Any]:
    """UI用の初期値辞書を生成する。"""

    return {name: profile.default for name, profile in profiles.items()}


def sanitize_entry(
    raw_entry: dict[str, Any], profiles: dict[str, ColumnProfile]
) -> dict[str, Any]:
    """フォーム入力をBi互換の値に変換する。"""

    sanitized: dict[str, Any] = {}
    for col, profile in profiles.items():
        value = raw_entry.get(col, profile.default)
        if profile.kind == "int":
            try:
                sanitized[col] = int(value)
            except (TypeError, ValueError) as exc:
                raise AnonymizationError(f"{col} は整数で入力してください") from exc
        elif profile.kind == "float":
            try:
                sanitized[col] = float(value)
            except (TypeError, ValueError) as exc:
                raise AnonymizationError(f"{col} は数値で入力してください") from exc
        else:
            sanitized[col] = "" if value is None else str(value).strip()
    return sanitized


def append_new_entry(
    base_df: pd.DataFrame, entry: dict[str, Any]
) -> tuple[pd.DataFrame, int]:
    """Biへ新規行を追加し、行数を維持したBi'を返す。"""

    entry_df = pd.DataFrame([entry], columns=base_df.columns)
    dtype_map = base_df.dtypes.to_dict()
    for col, dtype in dtype_map.items():
        try:
            entry_df[col] = entry_df[col].astype(dtype)
        except (ValueError, TypeError):
            if pdt.is_integer_dtype(dtype):
                entry_df[col] = (
                    pd.to_numeric(entry_df[col], errors="coerce").fillna(0).astype(dtype)
                )
            elif pdt.is_float_dtype(dtype):
                entry_df[col] = pd.to_numeric(entry_df[col], errors="coerce").astype(dtype)
            else:
                entry_df[col] = entry_df[col].astype(str)

    combined = pd.concat([base_df, entry_df], ignore_index=True)
    if len(combined) > len(base_df):
        combined = combined.iloc[-len(base_df) :].reset_index(drop=True)
    new_index = len(combined) - 1
    return combined, new_index


def _ensure_nonzero(noise: int, rng: np.random.Generator) -> int:
    """ノイズが0になった場合に±1へ調整する。"""

    if noise == 0:
        return int(rng.choice([-1, 1]))
    return int(noise)


def generate_ci(
    bi_prime: pd.DataFrame,
    algorithm: str,
    *,
    rng: np.random.Generator | None = None,
    target_index: int | None = None,
) -> pd.DataFrame:
    """選択アルゴリズムに基づきCiを生成する。"""

    if algorithm not in ALGORITHM_LABELS:
        raise AnonymizationError(f"未知のアルゴリズム: {algorithm}")

    if algorithm == "naive":
        return bi_prime.copy()

    rng = rng or np.random.default_rng()
    ci = bi_prime.copy()
    row_idx = target_index if target_index is not None else (len(ci) - 1)
    numeric_snapshot = ci.apply(pd.to_numeric, errors="coerce")
    binary_columns = {
        col
        for col in ci.columns
        if pdt.is_numeric_dtype(ci[col])
        and not numeric_snapshot[col].dropna().empty
        and set(numeric_snapshot[col].dropna().unique()).issubset({0.0, 1.0})
    }

    for col_idx, col in enumerate(ci.columns):
        series = ci[col]
        if col in binary_columns:
            continue
        if pdt.is_integer_dtype(series):
            original = int(series.iat[row_idx])
            span = max(1, int(series.max() - series.min()))
            window = max(2, span // 10 + 1)
            noise = int(rng.integers(-window, window + 1))
            noise = _ensure_nonzero(noise, rng)
            candidate = max(0, original + noise)
            upper = int(max(series.max(), candidate))
            candidate = int(np.clip(candidate, 0, upper))
            ci.iat[row_idx, col_idx] = candidate
        elif pdt.is_float_dtype(series):
            original = float(series.iat[row_idx])
            span = float(series.max() - series.min())
            scale = max(0.25, span * 0.05)
            noise = float(rng.normal(0.0, scale))
            if abs(noise) < 0.05:
                noise = 0.1 if noise >= 0 else -0.1
            candidate = original + noise
            upper = float(series.max()) + max(1.0, span * 0.05)
            candidate = float(np.clip(candidate, 0.0, upper))
            ci.iat[row_idx, col_idx] = round(candidate, 2)
        else:
            # カテゴリ列はフォーマット逸脱を避けるためにそのまま維持
            continue

    return ci


def run_anonymization(
    base_df: pd.DataFrame,
    profiles: dict[str, ColumnProfile],
    raw_entry: dict[str, Any],
    algorithm: str,
    *,
    rng: np.random.Generator | None = None,
) -> AnonymizationResult:
    """Bi, 入力値、アルゴリズム指定からBi'/Ciをまとめて生成する。"""

    sanitized = sanitize_entry(raw_entry, profiles)
    bi_prime, new_index = append_new_entry(base_df, sanitized)
    ci = generate_ci(bi_prime, algorithm, rng=rng, target_index=new_index)
    return AnonymizationResult(
        bi_prime=bi_prime,
        ci=ci,
        new_index=new_index,
        entry=sanitized,
    )
