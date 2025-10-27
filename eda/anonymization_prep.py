#!/usr/bin/env python3
"""匿名化前処理の素案: 年齢クリップと長尾分布のビニング案をまとめる。"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "data"
OUTPUT_DIR = BASE_DIR / "outputs" / "anonymization"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class AgeClipSummary:
    dataset: str
    rows_clipped: int
    before_max: float
    after_max: float
    sample_before_values: List[int]

    def to_dict(self) -> Dict[str, object]:
        return {
            "dataset": self.dataset,
            "rows_clipped": self.rows_clipped,
            "before_max": self.before_max,
            "after_max": self.after_max,
            "sample_before_values": self.sample_before_values,
        }


def load_dataset(path: Path, **kwargs) -> pd.DataFrame:
    if path.suffix.lower() != ".csv":
        raise ValueError(f"Unsupported file type: {path}")
    return pd.read_csv(path, **kwargs)


def clip_age(df: pd.DataFrame, dataset_label: str, max_age: int = 110) -> Tuple[pd.DataFrame, AgeClipSummary]:
    clipped = df.copy()
    over_mask = clipped["AGE"] > max_age
    rows_clipped = int(over_mask.sum())
    sample_values = (
        clipped.loc[over_mask, "AGE"].sort_values().astype(int).unique().tolist()[:10]
        if rows_clipped
        else []
    )
    before_max = float(clipped["AGE"].max())
    if rows_clipped:
        clipped.loc[over_mask, "AGE"] = max_age
    after_max = float(clipped["AGE"].max())
    summary = AgeClipSummary(
        dataset=dataset_label,
        rows_clipped=rows_clipped,
        before_max=before_max,
        after_max=after_max,
        sample_before_values=sample_values,
    )
    return clipped, summary


def build_bin_edges(series: pd.Series, quantiles: List[float]) -> List[float]:
    raw_edges = {float(series.min()), float(series.max())}
    for q in quantiles:
        value = float(series.quantile(q))
        raw_edges.add(value)
    edges = sorted(raw_edges)
    return edges


def summarize_bins(series: pd.Series, edges: List[float]) -> Dict[str, int]:
    bins = pd.cut(series, bins=edges, include_lowest=True, duplicates="drop")
    counts = bins.value_counts().sort_index()
    summary: Dict[str, int] = {}
    for interval, count in counts.items():
        left = interval.left
        right = interval.right
        # round to avoid lengthy decimals
        label = f"{round(left)}-{round(right)}"
        summary[label] = int(count)
    return summary


def generate_binning_plan(df: pd.DataFrame, columns: Dict[str, List[float]], dataset_label: str) -> Dict[str, object]:
    plan: Dict[str, object] = {}
    for column, quantiles in columns.items():
        if column not in df.columns:
            continue
        series = df[column]
        edges = build_bin_edges(series, quantiles)
        counts = summarize_bins(series, edges)
        plan[column] = {
            "quantiles": quantiles,
            "bin_edges": edges,
            "bin_counts": counts,
        }
    return plan


def main() -> None:
    hi_100k = load_dataset(DATA_DIR / "HI_100K.csv")
    hi_10k = load_dataset(DATA_DIR / "HI_10K.csv", encoding="utf-8-sig")

    ai_clipped, ai_summary = clip_age(hi_100k, "Ai")
    bi_clipped, bi_summary = clip_age(hi_10k, "Bi")

    age_summary = {
        "max_age": 110,
        "datasets": [ai_summary.to_dict(), bi_summary.to_dict()],
    }
    (OUTPUT_DIR / "age_clipping_summary.json").write_text(
        json.dumps(age_summary, ensure_ascii=False, indent=2)
    )

    long_tail_columns = {
        "encounter_count": [0.5, 0.75, 0.9, 0.95, 0.99, 0.995, 1.0],
        "num_procedures": [0.5, 0.75, 0.9, 0.95, 0.99, 0.995, 1.0],
        "num_medications": [0.5, 0.75, 0.9, 0.95, 0.99, 0.995, 1.0],
        "num_immunizations": [0.5, 0.75, 0.9, 0.95, 0.99, 1.0],
    }

    ai_binning_plan = generate_binning_plan(ai_clipped, long_tail_columns, "Ai")
    bi_binning_plan = generate_binning_plan(bi_clipped, long_tail_columns, "Bi")

    binning_summary = {
        "datasets": {
            "Ai": ai_binning_plan,
            "Bi": bi_binning_plan,
        },
        "notes": "bin_edges は匿名化時の事前ビニング候補を示す。最終的な桁丸めやノイズ幅に応じて調整してください。",
    }

    (OUTPUT_DIR / "long_tail_binning_plan.json").write_text(
        json.dumps(binning_summary, ensure_ascii=False, indent=2)
    )

    print("age_clipping_summary.json と long_tail_binning_plan.json を outputs/anonymization に出力しました")


if __name__ == "__main__":
    main()
