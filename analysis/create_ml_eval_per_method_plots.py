#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

sns.set_theme(style="whitegrid")

base = Path('experiments/summary_figures/ml_eval_summary.json')
data = json.loads(base.read_text(encoding='utf-8'))
df = pd.DataFrame(data)
out_dir = Path('experiments/summary_figures/ml_eval_by_method')
out_dir.mkdir(parents=True, exist_ok=True)

for method, sub in df.groupby('method'):
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharey=False)
    sub_sorted = sub.sort_values('param')
    sns.lineplot(data=sub_sorted, x='param', y='val_acc', marker='o', ax=axes[0], color='tab:blue')
    sns.lineplot(data=sub_sorted, x='param', y='attack_total', marker='o', ax=axes[1], color='tab:orange')
    axes[0].set(title=f"{method}: validation accuracy", xlabel='Setting', ylabel='Val accuracy')
    axes[1].set(title=f"{method}: attack success", xlabel='Setting', ylabel='Attack success (TOTAL)')
    for ax in axes:
        ax.grid(True, alpha=0.3)
        ax.tick_params(axis='x', rotation=20)
    fig.suptitle(f"{method} – ML evaluation", fontsize=14)
    fig.tight_layout()
    fig.savefig(out_dir / f"{method.replace(' ', '_')}_ml_eval.png", dpi=300)
    plt.close(fig)

print('Saved per-method plots to', out_dir)
