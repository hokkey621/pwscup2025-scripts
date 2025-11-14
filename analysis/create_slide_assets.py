#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from plot_experiment_summary import build_entries, load_dataframe, repo_root

sns.set_theme(style="whitegrid")

root = repo_root()
entries = build_entries(root)
df = load_dataframe(entries)[lambda d: d["group"] != "Differential Privacy"].reset_index(drop=True)

# --- 1. Best variant per method ---
best = df.sort_values("usefulness_score", ascending=False).groupby("group").head(1)

fig, ax1 = plt.subplots(figsize=(8, 5))
ax2 = ax1.twinx()

ax1.bar(best["group"], best["usefulness_score"], color="#4c78a8", alpha=0.8, label="Usefulness score")
ax2.plot(best["group"], best["anonymity_score_lr"], color="#72b7b2", marker="o", linewidth=2, label="Anonymity score")

ax1.set_ylabel("Usefulness score (0–80 pts)")
ax2.set_ylabel("Anonymity score (1 = safe, 0 = risky)")
ax1.set_ylim(0, 80)
ax2.set_ylim(0, 1)
ax1.set_title("Best-performing setting per method")

lines, labels = [], []
for ax in (ax1, ax2):
    line, label = ax.get_legend_handles_labels()
    lines.extend(line)
    labels.extend(label)
ax1.legend(lines, labels, loc="upper left")

out_dir = root / "experiments" / "summary_figures"
out_dir.mkdir(exist_ok=True, parents=True)
fig.tight_layout()
fig.savefig(out_dir / "best_method_summary.png", dpi=300)
plt.close(fig)

# --- 2. Evaluation flow diagram ---
fig, ax = plt.subplots(figsize=(8, 4))
ax.axis("off")
boxes = [
    ("Bi (original data)", (0.05, 0.7)),
    ("Ci generation\n(anonymization method)", (0.38, 0.7)),
    ("Quality check\n(util/check_csv)", (0.71, 0.7)),
    ("Utility scoring\n(evaluation/eval_all)", (0.2, 0.25)),
    ("Model training\n(analysis/xgbt_train)", (0.5, 0.25)),
    ("Attack simulation\n(attack/attack_example)", (0.8, 0.25)),
]

for text, (x, y) in boxes:
    rect = plt.Rectangle((x, y), 0.23, 0.18, linewidth=1.5, edgecolor="#4c78a8", facecolor="#e6f0ff")
    ax.add_patch(rect)
    ax.text(x + 0.115, y + 0.09, text, ha="center", va="center", fontsize=10)

arrows = [
    ((0.28, 0.79), (0.31, 0.79)),
    ((0.61, 0.79), (0.64, 0.79)),
    ((0.16, 0.43), (0.16, 0.7)),
    ((0.48, 0.43), (0.48, 0.7)),
    ((0.8, 0.43), (0.8, 0.7)),
]
for (x1, y1), (x2, y2) in arrows:
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="->", lw=1.5, color="#555"))

ax.text(0.16, 0.15, "Utility / anonymity reports", ha="center", fontsize=9)
ax.text(0.48, 0.15, "Trained Di", ha="center", fontsize=9)
ax.text(0.8, 0.15, "Attack success stats", ha="center", fontsize=9)
ax.set_title("Evaluation pipeline overview")

fig.tight_layout()
fig.savefig(out_dir / "evaluation_flow.png", dpi=300)
plt.close(fig)

print("Saved:")
print(out_dir / "best_method_summary.png")
print(out_dir / "evaluation_flow.png")
