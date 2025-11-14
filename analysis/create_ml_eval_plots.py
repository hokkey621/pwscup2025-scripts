#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

sns.set_theme(style="whitegrid")

base = Path('experiments/summary_figures/ml_eval_summary.json')
data = json.loads(base.read_text(encoding='utf-8'))
df = pd.DataFrame(data)

out_dir = Path('experiments/summary_figures')
out_dir.mkdir(parents=True, exist_ok=True)

# Scatter Val Accuracy vs Attack TOTAL
fig, ax = plt.subplots(figsize=(7, 5))
sns.scatterplot(data=df, x='val_acc', y='attack_total', hue='method', style='method', s=180, ax=ax)
for _, row in df.iterrows():
    ax.text(row['val_acc'] + 0.001, row['attack_total'] + 20, row['param'], fontsize=9)
ax.set_xlabel('Validation accuracy (Di, threshold=0.5)')
ax.set_ylabel('Attack success (TOTAL)')
ax.set_title('Model accuracy vs attack success per method')
ax.grid(True, alpha=0.3)
fig.tight_layout()
fig.savefig(out_dir / 'ml_eval_scatter.png', dpi=300)
plt.close(fig)

# Line plot per method showing trade-offs
fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=False)
for method, sub in df.groupby('method'):
    axes[0].plot(sub['param'], sub['val_acc'], marker='o', label=method)
    axes[1].plot(sub['param'], sub['attack_total'], marker='o', label=method)
axes[0].set(title='Validation accuracy by setting', ylabel='Val accuracy', xlabel='Setting')
axes[1].set(title='Attack success by setting', ylabel='Attack success (TOTAL)', xlabel='Setting')
for ax in axes:
    ax.grid(True, alpha=0.3)
    ax.legend()
fig.suptitle('Per-method ML evaluation trends', fontsize=14, y=1.02)
fig.tight_layout()
fig.savefig(out_dir / 'ml_eval_trends.png', dpi=300)
plt.close(fig)

print('Saved:')
print(out_dir / 'ml_eval_scatter.png')
print(out_dir / 'ml_eval_trends.png')
