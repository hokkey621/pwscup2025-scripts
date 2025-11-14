#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt

plt.rcParams['font.family'] = 'Hiragino Sans'

path = Path('experiments/summary_figures/model_compare_metrics.json')
data = json.loads(path.read_text(encoding='utf-8'))

x_use = []
y_attack = []
colors = []
labels = []

for label, metrics in data.items():
    x_use.append(metrics['usefulness'])
    y_attack.append(metrics['attack'])
    labels.append(label)
    colors.append('#43b0b1' if 't-outlier' in label else '#cccccc')

fig, ax = plt.subplots(figsize=(8, 5))
ax.scatter(x_use, y_attack, c=colors, s=120, edgecolor='black')
for x, y, label in zip(x_use, y_attack, labels):
    ax.text(x + 0.3, y + 20, label, fontsize=10)
ax.set_xlabel('有用性スコア (0–80)', fontsize=13, color='#43b0b1')
ax.set_ylabel('攻撃成功数 (TOTAL)', fontsize=13, color='#f04a51')
ax.tick_params(axis='x', colors='#43b0b1')
ax.tick_params(axis='y', colors='#f04a51')
ax.set_title('k-means (t-outlier) と他手法の比較', fontsize=15)
ax.grid(True, alpha=0.3)
fig.tight_layout()
fig.savefig('experiments/summary_figures/kmeans_vs_others_scatter.png', dpi=300)
plt.close(fig)
print('Saved kmeans_vs_others_scatter.png')
