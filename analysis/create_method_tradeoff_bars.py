#!/usr/bin/env python3
from __future__ import annotations

import matplotlib.pyplot as plt

records = [
    {
        "label": "t-outlier tail 5%",
        "usefulness": 77.843,
        "attack_total": 9353,
    },
    {
        "label": "Noise swap 1%",
        "usefulness": 67.18,
        "attack_total": 8897,
    },
    {
        "label": "k-anon k=2",
        "usefulness": 46.61,
        "attack_total": 6950,
    },
]

fig, ax1 = plt.subplots(figsize=(8, 5))
ax2 = ax1.twinx()

labels = [r["label"] for r in records]
usefulness = [r["usefulness"] for r in records]
attack = [r["attack_total"] for r in records]

ax1.bar(labels, usefulness, color="#4c78a8", alpha=0.85, label="Usefulness score (0–80)")
ax2.plot(labels, attack, color="#f58518", marker="o", linewidth=2.5, label="Attack success (lower = safer)")

ax1.set_ylabel("Usefulness score (0–80)")
ax2.set_ylabel("Attack success (TOTAL)")
ax1.set_ylim(0, 80)
ax2.set_ylim(6000, 10000)
ax1.set_title("Pros and cons per method")

lines, labels_legend = [], []
for ax in (ax1, ax2):
    line, label = ax.get_legend_handles_labels()
    lines.extend(line)
    labels_legend.extend(label)
ax1.legend(lines, labels_legend, loc="upper left")

for x, u, a in zip(labels, usefulness, attack):
    ax1.text(x, u + 1, f"{u:.1f}", ha="center")
    ax2.text(x, a + 50, f"{a}", color="#f58518", ha="center")

fig.tight_layout()
fig.savefig("experiments/summary_figures/method_tradeoff_bars.png", dpi=300)
plt.close(fig)
print("Saved experiments/summary_figures/method_tradeoff_bars.png")
