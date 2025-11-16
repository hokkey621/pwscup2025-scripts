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
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from pandas.api import types as ptypes
from scipy import stats
from sklearn.cluster import KMeans


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


@dataclass
class ColumnAnonymizationResult:
    column: str
    replaced: int
    tail_ratio: float


class TOutlierKMeansAnonymizer:
    """t分布を仮定した外れ値抽出＋k-meansによる代表値置換を行う。"""

    def __init__(
        self,
        *,
        tail_ratio: float,
        max_clusters: int,
        min_tail_samples: int = 5,
        random_state: int | None = None,
    ) -> None:
        if not 0 < tail_ratio < 0.5:
            raise ValueError("tail_ratio must be between 0 and 0.5")
        if max_clusters < 1:
            raise ValueError("max_clusters must be >= 1")
        self.tail_ratio = tail_ratio
        self.max_clusters = max_clusters
        self.min_tail_samples = max(1, min_tail_samples)
        self.random_state = random_state
        self.activity_log: list[ColumnAnonymizationResult] = []

    def _numeric_columns(self, df: pd.DataFrame) -> Iterable[str]:
        for col in df.columns:
            series = df[col]
            if not ptypes.is_numeric_dtype(series.dtype):
                continue
            # 0/1などのほぼ二値列は対象外にする
            if series.dropna().nunique() <= 2:
                continue
            yield col

    def _t_thresholds(self, values: pd.Series) -> tuple[float, float] | None:
        clean = values.dropna()
        if clean.shape[0] < 8:
            return None
        std = clean.std(ddof=1)
        if std == 0 or np.isnan(std):
            return None
        mean = clean.mean()
        dfree = max(int(clean.shape[0] - 1), 1)
        quant = stats.t.ppf(1 - self.tail_ratio / 2, dfree)
        if not np.isfinite(quant):
            return None
        delta = quant * std
        return mean - delta, mean + delta

    def _replace_with_kmeans(self, series: pd.Series, mask: pd.Series) -> pd.Series:
        tail_values = series[mask]
        if tail_values.empty or tail_values.shape[0] < self.min_tail_samples:
            return series
        unique_count = tail_values.nunique(dropna=True)
        n_clusters = min(self.max_clusters, unique_count, tail_values.shape[0])
        if n_clusters < 1:
            return series
        kmeans = KMeans(
            n_clusters=n_clusters,
            n_init=10,
            random_state=self.random_state,
        )
        arr = tail_values.to_numpy(dtype=np.float64).reshape(-1, 1)
        kmeans.fit(arr)
        centers = kmeans.cluster_centers_.flatten()
        labels = kmeans.labels_
        replaced = tail_values.copy()
        for idx, label in zip(tail_values.index, labels, strict=False):
            replaced.loc[idx] = centers[label]
        updated = series.copy()
        updated.loc[mask] = replaced
        return updated

    def _cast_back(self, original: pd.Series, numeric: pd.Series) -> pd.Series:
        if ptypes.is_integer_dtype(original.dtype):
            rounded = numeric.round().clip(lower=original.min(), upper=original.max())
            return rounded.astype(original.dtype)
        if ptypes.is_float_dtype(original.dtype):
            rounded = numeric.round(2)
            return rounded.astype(original.dtype)
        return numeric

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        result = df.copy()
        self.activity_log.clear()
        for col in self._numeric_columns(result):
            series = pd.to_numeric(result[col], errors="coerce").astype(float)
            thresholds = self._t_thresholds(series)
            if thresholds is None:
                continue
            lower, upper = thresholds
            mask = (series < lower) | (series > upper)
            if not mask.any():
                continue
            updated = self._replace_with_kmeans(series, mask)
            if updated.equals(series):
                continue
            casted = self._cast_back(result[col], updated)
            result[col] = casted
            self.activity_log.append(
                ColumnAnonymizationResult(
                    column=col,
                    replaced=int(mask.sum()),
                    tail_ratio=self.tail_ratio,
                )
            )
        return result


def generate_ci(
    df_bi: pd.DataFrame,
    *,
    tail_ratio: float,
    max_clusters: int,
    seed: int | None,
) -> pd.DataFrame:
    anonymizer = TOutlierKMeansAnonymizer(
        tail_ratio=tail_ratio,
        max_clusters=max_clusters,
        random_state=seed,
    )
    df_ci = anonymizer.transform(df_bi)
    if anonymizer.activity_log:
        for log in anonymizer.activity_log:
            print(
                f"[INFO] column={log.column} replaced={log.replaced} tail_ratio={log.tail_ratio:.3f}"
            )
    else:
        print("[INFO] 置換対象の外れ値は見つかりませんでした。")
    return df_ci


def run_anonymization(
    bi_path: Path,
    ci_path: Path,
    *,
    seed: int | None = None,
    tail_ratio: float,
    max_clusters: int,
) -> None:
    """Bi を読み込み、Ci を生成して保存するラッパー関数。"""
    seed_everything(seed)
    df_bi = pd.read_csv(bi_path)
    df_ci = generate_ci(
        df_bi,
        tail_ratio=tail_ratio,
        max_clusters=max_clusters,
        seed=seed,
    )
    ci_path.parent.mkdir(parents=True, exist_ok=True)
    CiDataFrame(df_ci).to_csv(str(ci_path))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="t分布＋k-means 外れ値置換")
    parser.add_argument("bi", help="入力となる Bi.csv")
    parser.add_argument("ci", help="出力する Ci.csv")
    parser.add_argument("--seed", type=int, default=42, help="乱数シード（任意）")
    parser.add_argument(
        "--tail-ratio",
        type=float,
        default=0.05,
        help="t分布で外れ値とみなす割合（例: 0.05 で5%%）",
    )
    parser.add_argument(
        "--max-clusters",
        type=int,
        default=3,
        help="外れ値領域に適用するk-meansの最大クラスタ数",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_anonymization(
        Path(args.bi),
        Path(args.ci),
        seed=args.seed,
        tail_ratio=args.tail_ratio,
        max_clusters=args.max_clusters,
    )


if __name__ == "__main__":
    main()
