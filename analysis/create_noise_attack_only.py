#!/usr/bin/env python3
from __future__ import annotations

import matplotlib.pyplot as plt

noise_percent = [1, 4, 10]
attack_total = [8897, 7307, 3177]

fig, ax = plt.subplots(figsize=(7, 4))
ax.plot(noise_percent, attack_total, marker='o', color='tab:orange')
ax.set_xlabel('Noise swap probability (%)')
ax.set_ylabel('Attack success (TOTAL)', color='tab:orange')
ax.set_title('Noise injection: effect on attack success')
ax.grid(True, alpha=0.3)
for x, y in zip(noise_percent, attack_total):
    ax.text(x, y + 50, f"{y}")
fig.tight_layout()
fig.savefig('experiments/summary_figures/noise_attack_only.png', dpi=300)
plt.close(fig)
print('Saved noise_attack_only.png')
