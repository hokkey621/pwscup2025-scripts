#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt

path = Path('experiments/summary_figures/model_compare_avg.json')
data = json.loads(path.read_text(encoding='utf-8'))
labels = list(data.keys())
usefulness = [data[label]['usefulness'] for label in labels]
attack = [data[label]['attack'] for label in labels]

fig, ax1 = plt.subplots(figsize=(6, 4))
ax2 = ax1.twinx()
ax1.bar(labels, usefulness, color='#4c78a8', alpha=0.8, label='Usefulness (0–80)')
ax2.plot(labels, attack, color='#f58518', marker='o', linewidth=2.5, label='Attack success (lower is safer)')
ax1.set_ylabel('Usefulness score (avg)')
ax2.set_ylabel('Attack success (TOTAL, avg)')
ax1.set_ylim(0, 80)
ax2.set_ylim(0, 10000)
ax1.set_title('Category comparison (avg scores)')

lines, labels_legend = [], []
for ax in (ax1, ax2):
    line, label = ax.get_legend_handles_labels()
    lines.extend(line)
    labels_legend.extend(label)
ax1.legend(lines, labels_legend, loc='upper center')

for x, u, a in zip(labels, usefulness, attack):
    ax1.text(x, u + 1, f"{u:.1f}", ha='center')
    ax2.text(x, a + 60, f"{a:.0f}", color='#f58518', ha='center')

fig.tight_layout()
fig.savefig('experiments/summary_figures/category_avg_tradeoff.png', dpi=300)
plt.close(fig)
print('Saved category_avg_tradeoff.png')
