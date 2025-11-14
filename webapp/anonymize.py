"""匿名化処理およびフォーム入力整形ロジック。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import json

import numpy as np
import pandas as pd
from pandas.api import types as pdt
from scipy import stats as scipy_stats
from sklearn.cluster import KMeans

from . import DEFAULT_BI_PATH


ALGORITHM_OPTIONS: list[tuple[str, str]] = [
    ("naive", "アルゴリズムA: ナイーブ加工 (そのままコピー)"),
    ("main", "アルゴリズムB: 本命加工 (ノイズ付与)"),
    ("k_anonymity", "アルゴリズムC: k匿名化 (k=2)"),
    ("t_outlier_kmeans", "アルゴリズムD: k-means外れ値置換 (5%外れ値)"),
]
ALGORITHM_LABELS: Dict[str, str] = dict(ALGORITHM_OPTIONS)

K_ANONYMITY_TARGET = 2
KMEANS_TAIL_RATIO = 0.05
KMEANS_MAX_CLUSTERS = 3
KMEANS_MIN_TAIL_SAMPLES = 5


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


def _load_column_specs() -> dict[str, dict[str, Any]]:
    range_path = DEFAULT_BI_PATH.parent / "columns_range.json"
    with range_path.open(encoding="utf-8") as fp:
        payload = json.load(fp)
    columns = payload.get("columns")
    if not isinstance(columns, dict):
        raise AnonymizationError("columns_range.json の形式が不正です")
    return columns


COLUMN_SPECS: dict[str, dict[str, Any]] = _load_column_specs()


def _choose_mode_value(series: pd.Series) -> Any:
    """カテゴリ列などで最頻値を安定して取得する。"""

    if series.empty:
        return ""
    mode_vals = series.mode(dropna=True)
    if mode_vals.empty:
        return ""
    if len(mode_vals) == 1:
        return mode_vals.iloc[0]
    as_str = mode_vals.astype(str)
    winner = min(as_str)
    winner_idx = as_str[as_str == winner].index[0]
    return mode_vals.loc[winner_idx]


def _aggregate_numeric(series: pd.Series, spec: dict[str, Any]) -> float | int:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().any():
        agg_val = float(numeric.mean())
    else:
        agg_val = float(spec.get("min", 0.0))
    min_val = float(spec.get("min", agg_val))
    max_val = float(spec.get("max", agg_val))
    agg_val = float(np.clip(agg_val, min_val, max_val))
    places = spec.get("max_decimal_places")
    if places is not None:
        places_int = int(places)
        agg_val = round(agg_val, places_int)
        if places_int == 0:
            return int(agg_val)
    return agg_val


def _aggregate_date(series: pd.Series, spec: dict[str, Any]) -> str:
    cleaned = pd.to_datetime(series, errors="coerce").dropna()
    if cleaned.empty:
        candidate = pd.to_datetime(spec.get("min"))
    else:
        candidate = cleaned.sort_values().iloc[len(cleaned) // 2]
    min_dt = pd.to_datetime(spec.get("min"))
    max_dt = pd.to_datetime(spec.get("max"))
    candidate = min(max(candidate, min_dt), max_dt)
    return candidate.strftime("%Y-%m-%d")


def _aggregate_group_block(block: pd.DataFrame) -> dict[str, Any]:
    aggregated: dict[str, Any] = {}
    for col in block.columns:
        spec = COLUMN_SPECS.get(col, {})
        col_type = spec.get("type")
        if col_type == "number":
            aggregated[col] = _aggregate_numeric(block[col], spec)
        elif col_type == "date":
            aggregated[col] = _aggregate_date(block[col], spec)
        else:
            aggregated[col] = _choose_mode_value(block[col])
    return aggregated


def _build_k_anonymous_groups(
    num_rows: int, k: int, rng: np.random.Generator
) -> list[list[int]]:
    if k <= 0:
        raise AnonymizationError("k は1以上で指定してください")
    if num_rows < k:
        raise AnonymizationError(
            f"k={k} に対して行数 {num_rows} が不足しています"
        )
    order = rng.permutation(num_rows)
    groups: list[list[int]] = []
    start = 0
    while start < num_rows:
        end = min(start + k, num_rows)
        block = order[start:end].tolist()
        if len(block) < k and groups:
            groups[-1].extend(block)
        else:
            groups.append(block)
        start = end
    return groups


def _apply_k_anonymity(
    bi_prime: pd.DataFrame,
    *,
    rng: np.random.Generator,
    k: int = K_ANONYMITY_TARGET,
) -> pd.DataFrame:
    groups = _build_k_anonymous_groups(len(bi_prime), k, rng)
    result = bi_prime.copy()
    for rows in groups:
        block = bi_prime.iloc[rows]
        aggregated = _aggregate_group_block(block)
        for col, value in aggregated.items():
            col_pos = result.columns.get_loc(col)
            result.iloc[rows, col_pos] = value
    return result


class TOutlierKMeansAnonymizer:
    """t分布を仮定した外れ値をk-meansで集約する。"""

    def __init__(
        self,
        *,
        tail_ratio: float,
        max_clusters: int,
        min_tail_samples: int,
        rng: np.random.Generator,
    ) -> None:
        if not 0 < tail_ratio < 0.5:
            raise ValueError("tail_ratio must be between 0 and 0.5")
        if max_clusters < 1:
            raise ValueError("max_clusters must be >= 1")
        self.tail_ratio = tail_ratio
        self.max_clusters = max_clusters
        self.min_tail_samples = max(1, min_tail_samples)
        self.rng = rng

    def _numeric_columns(self, df: pd.DataFrame) -> list[str]:
        targets: list[str] = []
        for col in df.columns:
            series = df[col]
            if not pdt.is_numeric_dtype(series.dtype):
                continue
            if series.dropna().nunique() <= 2:
                continue
            targets.append(col)
        return targets

    def _t_thresholds(self, series: pd.Series) -> tuple[float, float] | None:
        clean = series.dropna()
        if clean.shape[0] < 8:
            return None
        std = float(clean.std(ddof=1))
        if std == 0 or np.isnan(std):
            return None
        mean = float(clean.mean())
        dof = max(int(clean.shape[0] - 1), 1)
        quant = scipy_stats.t.ppf(1 - self.tail_ratio / 2, dof)
        if not np.isfinite(quant):
            return None
        delta = float(quant * std)
        return mean - delta, mean + delta

    def _random_state(self) -> int:
        return int(self.rng.integers(0, np.iinfo(np.int32).max))

    def _replace_with_kmeans(self, series: pd.Series, mask: pd.Series) -> pd.Series:
        tail_values = series[mask]
        if tail_values.empty or tail_values.shape[0] < self.min_tail_samples:
            return series
        unique_count = tail_values.nunique(dropna=True)
        n_clusters = min(self.max_clusters, unique_count, tail_values.shape[0])
        if n_clusters < 1:
            return series
        kmeans = KMeans(n_clusters=n_clusters, n_init=10, random_state=self._random_state())
        arr = tail_values.to_numpy(dtype=np.float64).reshape(-1, 1)
        kmeans.fit(arr)
        centers = kmeans.cluster_centers_.flatten()
        labels = kmeans.labels_
        updated = series.copy()
        for idx, label in zip(tail_values.index, labels, strict=False):
            updated.loc[idx] = centers[label]
        return updated

    def _cast_back(self, original: pd.Series, numeric: pd.Series) -> pd.Series:
        if pdt.is_integer_dtype(original.dtype):
            rounded = numeric.round().clip(lower=original.min(), upper=original.max())
            return rounded.astype(original.dtype)
        if pdt.is_float_dtype(original.dtype):
            rounded = numeric.round(2)
            return rounded.astype(original.dtype)
        return numeric

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        result = df.copy()
        for col in self._numeric_columns(result):
            series = pd.to_numeric(result[col], errors="coerce").astype(float)
            thresholds = self._t_thresholds(series)
            if thresholds is None:
                continue
            lower, upper = thresholds
            mask = (series < lower) | (series > upper)
            if not mask.any():
                continue
            replaced = self._replace_with_kmeans(series, mask)
            if replaced.equals(series):
                continue
            casted = self._cast_back(result[col], replaced)
            result[col] = casted
        return result


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


def _apply_noise_ci(
    bi_prime: pd.DataFrame,
    *,
    rng: np.random.Generator,
    target_index: int | None = None,
) -> pd.DataFrame:
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
            continue
    return ci


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

    if algorithm == "main":
        return _apply_noise_ci(bi_prime, rng=rng, target_index=target_index)

    if algorithm == "k_anonymity":
        return _apply_k_anonymity(bi_prime, rng=rng)

    if algorithm == "t_outlier_kmeans":
        anonymizer = TOutlierKMeansAnonymizer(
            tail_ratio=KMEANS_TAIL_RATIO,
            max_clusters=KMEANS_MAX_CLUSTERS,
            min_tail_samples=KMEANS_MIN_TAIL_SAMPLES,
            rng=rng,
        )
        return anonymizer.transform(bi_prime)

    raise AnonymizationError(f"アルゴリズム {algorithm} は未実装です")


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
