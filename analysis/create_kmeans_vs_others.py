#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt

path = Path('experiments/summary_figures/model_compare_metrics.json')
data = json.loads(path.read_text(encoding='utf-8'))

items = list(data.items())
labels = [name for name, _ in items]
usefulness = [entry['usefulness'] for _, entry in items]
attack = [entry['attack'] for _, entry in items]

# Usefulness comparison
fig, ax = plt.subplots(figsize=(10, 4))
ax.bar(labels, usefulness, color=['#4c78a8' if 't-outlier' in label else '#9ecae9' for label in labels])
ax.set_ylabel('Usefulness score (0–80)')
ax.set_title('Usefulness comparison: t-outlier vs others')
ax.tick_params(axis='x', rotation=30)
for x, y in zip(labels, usefulness):
    ax.text(x, y + 0.5, f"{y:.1f}", ha='center')
fig.tight_layout()
fig.savefig('experiments/summary_figures/usefulness_toutlier_vs_others.png', dpi=300)
plt.close(fig)

# Attack comparison
fig, ax = plt.subplots(figsize=(10, 4))
ax.bar(labels, attack, color=['#f58518' if 't-outlier' in label else '#fbb4a9' for label in labels])
ax.set_ylabel('Attack success (TOTAL)')
ax.set_title('Attack success: lower is better')
ax.tick_params(axis='x', rotation=30)
for x, y in zip(labels, attack):
    ax.text(x, y + 40, f"{y}", ha='center')
fig.tight_layout()
fig.savefig('experiments/summary_figures/attack_toutlier_vs_others.png', dpi=300)
plt.close(fig)

print('Saved usefulness_toutlier_vs_others.png and attack_toutlier_vs_others.png')
