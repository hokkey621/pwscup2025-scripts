#!/usr/bin/env python3
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


@dataclass
class ExperimentEntry:
    name: str
    group: str
    param_value: float
    param_label: str
    metrics_path: Path

    def load_metrics(self) -> dict[str, float]:
        with self.metrics_path.open("r", encoding="utf-8") as fp:
            return json.load(fp)


def build_entries(base: Path) -> List[ExperimentEntry]:
    def p(*parts: str) -> Path:
        return base.joinpath(*parts)

    dp_entries = [
        ("dp_eps05_strict", 0.5),
        ("dp_eps10_moderate", 1.0),
        ("dp_eps20_balanced", 2.0),
        ("dp_eps40_relaxed", 4.0),
        ("dp_eps80_loose", 8.0),
    ]
    noise_entries = [
        ("noise_lvl1_soft", 0.01),
        ("noise_lvl2_mild", 0.02),
        ("noise_lvl3_balanced", 0.04),
        ("noise_lvl4_strong", 0.07),
        ("noise_lvl5_extreme", 0.10),
    ]
    k_entries = [
        ("method_k_anonymity_k02", 2),
        ("method_k_anonymity_k05", 5),
        ("method_k_anonymity_k08", 8),
        ("method_k_anonymity_k15", 15),
    ]
    t_entries = [
        ("t_outlier_p001", 0.01),
        ("t_outlier_p005", 0.05),
        ("t_outlier_p010", 0.10),
    ]

    entries: List[ExperimentEntry] = []

    for name, eps in dp_entries:
        entries.append(
            ExperimentEntry(
                name=name,
                group="Differential Privacy",
                param_value=eps,
                param_label=f"ε={eps}",
                metrics_path=p("experiments", name, "reports", "metrics.json"),
            )
        )

    for name, swap_prob in noise_entries:
        entries.append(
            ExperimentEntry(
                name=name,
                group="Noise Injection",
                param_value=swap_prob,
                param_label=f"swap {swap_prob*100:.0f}%",
                metrics_path=p("experiments", name, "reports", "metrics.json"),
            )
        )

    for name, kval in k_entries:
        entries.append(
            ExperimentEntry(
                name=name,
                group="k-Anonymity",
                param_value=kval,
                param_label=f"k={kval}",
                metrics_path=p("experiments", name, "reports", "metrics.json"),
            )
        )

    t_metrics = {
        0.01: "t_outlier_p001_metrics.json",
        0.05: "t_outlier_p005_metrics.json",
        0.10: "t_outlier_p010_metrics.json",
    }
    for tail_ratio, filename in t_metrics.items():
        entries.append(
            ExperimentEntry(
                name=f"T-Outlier {tail_ratio:.2%}",
                group="t-Outlier k-means",
                param_value=tail_ratio,
                param_label=f"tail {tail_ratio:.0%}",
                metrics_path=p("experiments", "method_t_outlier_kmeans", "reports", filename),
            )
        )

    return entries


def load_dataframe(entries: List[ExperimentEntry]) -> pd.DataFrame:
    rows = []
    for entry in entries:
        if not entry.metrics_path.exists():
            continue
        metrics = entry.load_metrics()
        rows.append(
            {
                "variant": entry.name,
                "group": entry.group,
                "param_value": entry.param_value,
                "param_label": entry.param_label,
                **metrics,
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        raise RuntimeError("No metrics were loaded. Check file paths.")
    df["usefulness_score"] = df["ci_utility"]
    df["anonymity_score_lr"] = 1.0 - df["lr_asthma_max_abs"]
    df["anonymity_score_stats"] = 1.0 - df["stats_diff_max_abs"]
    return df[df["group"] != "Differential Privacy"].reset_index(drop=True)


def plot_scatter(df: pd.DataFrame, out_dir: Path) -> None:
    sns.set_theme(style="whitegrid")

    fig, axes = plt.subplots(1, 2, figsize=(14, 6), sharey=True)

    sns.scatterplot(
        data=df,
        x="anonymity_score_lr",
        y="usefulness_score",
        hue="group",
        style="group",
        s=140,
        ax=axes[0],
    )
    for _, row in df.iterrows():
        axes[0].text(
            row["anonymity_score_lr"] + 0.01,
            row["usefulness_score"] + 0.5,
            row["param_label"],
            fontsize=8,
        )
    axes[0].set_title("Anonymity (model diff) vs Usefulness")
    axes[0].set_xlabel("Anonymity score (1 = safe, 0 = risky)")
    axes[0].set_ylabel("Usefulness score (0–80 points)")

    sns.scatterplot(
        data=df,
        x="anonymity_score_stats",
        y="usefulness_score",
        hue="group",
        style="group",
        s=140,
        ax=axes[1],
        legend=False,
    )
    for _, row in df.iterrows():
        axes[1].text(
            row["anonymity_score_stats"] + 0.01,
            row["usefulness_score"] + 0.5,
            row["param_label"],
            fontsize=8,
        )
    axes[1].set_title("Anonymity (stat diff) vs Usefulness")
    axes[1].set_xlabel("Anonymity score (1 = safe, 0 = risky)")
    axes[0].set_xlim(0, 1)
    axes[1].set_xlim(0, 1)
    axes[0].set_ylim(0, 80)
    axes[1].set_ylim(0, 80)

    handles, labels = axes[0].get_legend_handles_labels()
    axes[0].legend(handles, labels, title="Method", fontsize=10, title_fontsize=12)
    fig.tight_layout()
    out_path = out_dir / "scatter_ci_utility.png"
    fig.savefig(out_path, dpi=300)
    plt.close(fig)


def plot_group_trends(df: pd.DataFrame, out_dir: Path) -> None:
    sns.set_theme(style="whitegrid")
    groups = df["group"].unique()
    fig, axes = plt.subplots(len(groups), 2, figsize=(12, 3 * len(groups)), squeeze=False)

    for row_idx, group in enumerate(groups):
        sub = df[df["group"] == group].sort_values("param_value")
        ax_use = axes[row_idx, 0]
        ax_anon = axes[row_idx, 1]

        sns.lineplot(
            data=sub,
            x="param_value",
            y="usefulness_score",
            marker="o",
            ax=ax_use,
            color="tab:blue",
        )
        ax_use.set(
            title=f"{group} – Usefulness",
            xlabel="Parameter value",
            ylabel="Usefulness score (0–80 pts)",
        )
        ax_use.set_ylim(0, 80)
        ax_use.grid(True, alpha=0.3)

        sns.lineplot(
            data=sub,
            x="param_value",
            y="anonymity_score_lr",
            marker="o",
            ax=ax_anon,
            color="tab:green",
        )
        ax_anon.set(
            title=f"{group} – Anonymity",
            xlabel="Parameter value",
            ylabel="Anonymity score (1 = safe, 0 = risky)",
        )
        ax_anon.set_ylim(0, 1)
        ax_anon.grid(True, alpha=0.3)

    fig.suptitle("Per-method parameter trade-offs", fontsize=14, y=1.02)
    fig.tight_layout()
    out_path = out_dir / "group_trends.png"
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    root = repo_root()
    entries = build_entries(root)
    df = load_dataframe(entries)

    out_dir = root / "experiments" / "summary_figures"
    out_dir.mkdir(parents=True, exist_ok=True)

    plot_scatter(df, out_dir)
    plot_group_trends(df, out_dir)

    csv_path = out_dir / "metrics_summary.csv"
    df.to_csv(csv_path, index=False)
    print(f"Saved summary CSV to {csv_path}")
    print(f"Scatter plot  : {out_dir / 'scatter_ci_utility.png'}")
    print(f"Trend plot    : {out_dir / 'group_trends.png'}")


if __name__ == "__main__":
    main()
