from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "data"
OUTPUT_DIR = BASE_DIR / "outputs"
FIG_DIR = OUTPUT_DIR / "figures"
TABLE_DIR = OUTPUT_DIR / "tables"
MPLCONFIG_DIR = BASE_DIR / ".mplconfig"

for directory in (OUTPUT_DIR, FIG_DIR, TABLE_DIR, MPLCONFIG_DIR):
    directory.mkdir(exist_ok=True)

os.environ["MPLCONFIGDIR"] = str(MPLCONFIG_DIR)

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib import font_manager
import pandas as pd
import seaborn as sns

FONT_CANDIDATES = [
    "Hiragino Sans",
    "Hiragino Kaku Gothic ProN",
    "Yu Gothic",
    "YuGothic",
    "Noto Sans CJK JP",
    "IPAexGothic",
    "Meiryo",
    "TakaoPGothic",
]

def _resolve_font_name() -> str:
    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in FONT_CANDIDATES:
        if name in available:
            return name
    if "AppleGothic" in available:
        return "AppleGothic"
    return "DejaVu Sans"


SELECTED_FONT = _resolve_font_name()

sns.set_theme(style="whitegrid", rc={"axes.unicode_minus": False, "font.family": SELECTED_FONT})

matplotlib.rcParams["font.family"] = [SELECTED_FONT]
matplotlib.rcParams["font.sans-serif"] = [SELECTED_FONT, "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False


def load_dataset(path: Path, **kwargs) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, **kwargs)
    raise ValueError(f"Unsupported file type: {path}")


def summarize_numeric(df: pd.DataFrame, label: str) -> pd.DataFrame:
    numeric_cols = df.select_dtypes(include="number")
    desc = numeric_cols.describe(percentiles=[0.25, 0.5, 0.75, 0.95, 0.99]).T
    desc.insert(0, "dataset", label)
    return desc.reset_index().rename(columns={"index": "column"})


def summarize_categorical(df: pd.DataFrame, categorical_cols: List[str], label: str) -> pd.DataFrame:
    rows = []
    for col in categorical_cols:
        if col not in df.columns:
            continue
        counts = df[col].value_counts(dropna=False)
        total = counts.sum()
        for category, count in counts.items():
            ratio = count / total if total else 0.0
            rows.append(
                {
                    "dataset": label,
                    "column": col,
                    "value": category,
                    "count": int(count),
                    "ratio": ratio,
                }
            )
    return pd.DataFrame(rows)


def flag_prevalence(df: pd.DataFrame, flag_cols: List[str], label: str) -> pd.DataFrame:
    rows = []
    for col in flag_cols:
        if col not in df.columns:
            continue
        counts = df[col].value_counts()
        total = counts.sum()
        for flag_value in sorted(counts.index):
            ratio = counts[flag_value] / total if total else 0.0
            rows.append(
                {
                    "dataset": label,
                    "flag": col,
                    "value": flag_value,
                    "count": counts[flag_value],
                    "ratio": ratio,
                }
            )
    return pd.DataFrame(rows)


def calc_max_decimal_places(series: pd.Series) -> int:
    max_dp = 0
    for value in series.dropna():
        text = str(value)
        if "." in text:
            decimals = text.split(".")[1].rstrip("0")
            max_dp = max(max_dp, len(decimals))
    return max_dp


def summarize_ranges(spec: Dict, datasets: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for col_name, meta in spec.get("columns", {}).items():
        row = {"column": col_name, "type": meta.get("type")}
        if meta.get("type") == "number":
            spec_min = meta.get("min")
            spec_max = meta.get("max")
            spec_decimals = meta.get("max_decimal_places")
            row.update({"spec_min": spec_min, "spec_max": spec_max, "spec_max_decimals": spec_decimals})
            for label, df in datasets.items():
                if col_name not in df.columns:
                    continue
                series = df[col_name].dropna()
                row[f"{label}_min"] = series.min()
                row[f"{label}_max"] = series.max()
                row[f"{label}_max_decimals"] = calc_max_decimal_places(series)
                row[f"{label}_min_violation"] = spec_min is not None and series.min() < spec_min
                row[f"{label}_max_violation"] = spec_max is not None and series.max() > spec_max
                row[f"{label}_decimal_violation"] = (
                    spec_decimals is not None and row[f"{label}_max_decimals"] > spec_decimals
                )
        elif meta.get("type") == "category":
            allowed = set(meta.get("values", []))
            row["allowed_values"] = ", ".join(sorted(allowed))
            for label, df in datasets.items():
                if col_name not in df.columns:
                    continue
                values = set(df[col_name].dropna().unique())
                unexpected = values - allowed
                row[f"{label}_unexpected_values"] = ", ".join(sorted(unexpected)) if unexpected else ""
        rows.append(row)
    return pd.DataFrame(rows)


def plot_age_distribution(ai: pd.DataFrame, bi: pd.DataFrame, figure_path: Path) -> None:
    plot_df = pd.concat(
        [ai[["AGE"]].assign(dataset="Ai"), bi[["AGE"]].assign(dataset="Bi")],
        ignore_index=True,
    )
    plt.figure(figsize=(8, 5))
    sns.histplot(data=plot_df, x="AGE", hue="dataset", stat="density", common_norm=False, bins=40, alpha=0.5)
    plt.title("年齢分布の比較")
    plt.xlabel("年齢")
    plt.ylabel("密度")
    plt.tight_layout()
    plt.savefig(figure_path, dpi=150)
    plt.close()


def plot_race_distribution(ai: pd.DataFrame, bi: pd.DataFrame, figure_path: Path) -> None:
    def compute_ratio(df: pd.DataFrame, label: str) -> pd.DataFrame:
        counts = df["RACE"].value_counts(normalize=True).rename("ratio").reset_index()
        counts["dataset"] = label
        counts = counts.rename(columns={"index": "RACE"})
        return counts

    plot_df = pd.concat([compute_ratio(ai, "Ai"), compute_ratio(bi, "Bi")], ignore_index=True)
    plt.figure(figsize=(8, 5))
    sns.barplot(data=plot_df, x="RACE", y="ratio", hue="dataset")
    plt.title("人種カテゴリ比率の比較")
    plt.ylabel("比率")
    plt.xlabel("RACE")
    plt.xticks(rotation=30)
    plt.tight_layout()
    plt.savefig(figure_path, dpi=150)
    plt.close()


def plot_bmi_by_membership(ai_with_membership: pd.DataFrame, figure_path: Path) -> None:
    plt.figure(figsize=(7, 5))
    sns.boxplot(data=ai_with_membership, x="is_member", y="mean_bmi")
    plt.title("メンバーシップ有無別のBMI分布 (Ai)")
    plt.xlabel("is_member (0=非メンバー, 1=メンバー)")
    plt.ylabel("mean_bmi")
    plt.tight_layout()
    plt.savefig(figure_path, dpi=150)
    plt.close()


def plot_ai_numeric_distributions(ai: pd.DataFrame, figure_path: Path) -> None:
    numeric_cols = ["encounter_count", "num_medications", "mean_bmi", "mean_weight"]
    fig, axes = plt.subplots(2, 2, figsize=(10, 8))
    for ax, col in zip(axes.flatten(), numeric_cols):
        sns.histplot(ai[col], ax=ax, bins=40, color="#1f77b4")
        ax.set_title(f"{col} 分布 (Ai)")
        ax.set_xlabel(col)
        ax.set_ylabel("件数")
    plt.tight_layout()
    plt.savefig(figure_path, dpi=150)
    plt.close()


def main() -> None:
    hi_10k = load_dataset(DATA_DIR / "HI_10K.csv", encoding="utf-8-sig")
    hi_100k = load_dataset(DATA_DIR / "HI_100K.csv")
    hi_ans = load_dataset(DATA_DIR / "HI_ans.csv", header=None, names=["is_member"])

    if len(hi_ans) != len(hi_100k):
        raise ValueError("HI_ans.csv と HI_100K.csv の行数が一致しません")

    hi_100k_with_membership = hi_100k.copy()
    hi_100k_with_membership["is_member"] = hi_ans["is_member"].astype(int)

    numerical_summary = pd.concat(
        [
            summarize_numeric(hi_100k, "Ai"),
            summarize_numeric(hi_10k, "Bi"),
            summarize_numeric(hi_100k_with_membership[hi_100k_with_membership["is_member"] == 1], "Ai_member"),
        ],
        ignore_index=True,
    )
    numerical_summary.to_csv(TABLE_DIR / "numeric_summary.csv", index=False)

    mean_pivot = numerical_summary.pivot_table(index="column", columns="dataset", values="mean")
    mean_pivot["Bi_minus_Ai"] = mean_pivot.get("Bi") - mean_pivot.get("Ai")
    mean_pivot["Ai_member_minus_Ai"] = mean_pivot.get("Ai_member") - mean_pivot.get("Ai")
    mean_pivot.to_csv(TABLE_DIR / "numeric_mean_compare.csv")

    categorical_cols = ["GENDER", "RACE", "ETHNICITY"]
    categorical_summary = pd.concat(
        [
            summarize_categorical(hi_100k, categorical_cols, "Ai"),
            summarize_categorical(hi_10k, categorical_cols, "Bi"),
        ],
        ignore_index=True,
    )
    categorical_summary.to_csv(TABLE_DIR / "categorical_distribution.csv", index=False)

    flag_cols = ["asthma_flag", "stroke_flag", "obesity_flag", "depression_flag"]
    flag_summary = pd.concat(
        [
            flag_prevalence(hi_100k, flag_cols, "Ai"),
            flag_prevalence(hi_10k, flag_cols, "Bi"),
        ],
        ignore_index=True,
    )
    flag_summary.to_csv(TABLE_DIR / "flag_prevalence.csv", index=False)

    flag_cooccurrence = pd.concat(
        [
            hi_100k[flag_cols].value_counts().reset_index(name="count").assign(dataset="Ai"),
            hi_10k[flag_cols].value_counts().reset_index(name="count").assign(dataset="Bi"),
        ],
        ignore_index=True,
    )
    flag_cooccurrence["ratio"] = flag_cooccurrence.groupby("dataset")["count"].transform(
        lambda s: s / s.sum() if s.sum() else 0
    )
    flag_cooccurrence.to_csv(TABLE_DIR / "flag_cooccurrence.csv", index=False)

    missing_summary = pd.DataFrame(
        {
            "column": hi_100k.columns,
            "missing_Ai": hi_100k.isna().sum().values,
            "missing_Bi": hi_10k.isna().sum().values,
        }
    )
    missing_summary.to_csv(TABLE_DIR / "missing_values.csv", index=False)

    unique_summary = pd.DataFrame(
        {
            "column": hi_100k.columns,
            "Ai_unique": hi_100k.nunique().values,
            "Bi_unique": hi_10k.nunique().values,
        }
    )
    unique_summary.to_csv(TABLE_DIR / "unique_counts.csv", index=False)

    dataset_overview = pd.DataFrame(
        [
            {"dataset": "Ai", "row_count": len(hi_100k)},
            {"dataset": "Bi", "row_count": len(hi_10k)},
        ]
    )
    dataset_overview.to_csv(TABLE_DIR / "dataset_overview.csv", index=False)

    spec = json.loads((DATA_DIR / "columns_range.json").read_text())
    range_summary = summarize_ranges(spec, {"Ai": hi_100k, "Bi": hi_10k})
    range_summary.to_csv(TABLE_DIR / "range_check.csv", index=False)

    plot_age_distribution(hi_100k, hi_10k, FIG_DIR / "age_distribution.png")
    plot_race_distribution(hi_100k, hi_10k, FIG_DIR / "race_distribution.png")
    plot_bmi_by_membership(hi_100k_with_membership, FIG_DIR / "bmi_by_membership.png")
    plot_ai_numeric_distributions(hi_100k, FIG_DIR / "ai_numeric_distributions.png")

    membership_rate = hi_100k_with_membership["is_member"].mean()
    with open(TABLE_DIR / "membership_summary.json", "w", encoding="utf-8") as f:
        json.dump({"member_count": int(hi_ans["is_member"].sum()), "member_ratio": membership_rate}, f, ensure_ascii=False, indent=2)

    print("EDA outputs generated under", OUTPUT_DIR)


if __name__ == "__main__":
    main()
