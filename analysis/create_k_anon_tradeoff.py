#!/usr/bin/env python3
from __future__ import annotations

import matplotlib.pyplot as plt

plt.rcParams['font.family'] = 'Hiragino Sans'

k_values = [2, 5, 8, 15]
attack_total = [6950, 6900, 6880, 6850]
usefulness = [46.61, 42.05, 41.17, 39.50]

fig, ax1 = plt.subplots(figsize=(7.5, 4.5))
ax1.plot(k_values, attack_total, marker='o', color='#f04a51')
ax1.set_xlabel('k値', fontsize=13)
ax1.set_ylabel('攻撃成功数 (TOTAL)', color='#f04a51', fontsize=13)
ax1.tick_params(axis='both', colors='#000000', labelsize=12)
ax1.set_title('k匿名化: kと攻撃成功数', fontsize=15)
ax1.grid(True, alpha=0.3)
for x, y in zip(k_values, attack_total):
    ax1.text(x, y + 20, f"{y}", color='#000000', ha='center', fontsize=12)
fig.tight_layout()
fig.savefig('experiments/summary_figures/k_anon_attack_vs_k.png', dpi=300)
plt.close(fig)

fig, ax2 = plt.subplots(figsize=(7.5, 4.5))
ax2.plot(k_values, usefulness, marker='o', color='#43b0b1')
ax2.set_xlabel('k値', fontsize=13)
ax2.set_ylabel('有用性スコア (0–80)', color='#43b0b1', fontsize=13)
ax2.tick_params(axis='both', colors='#000000', labelsize=12)
ax2.set_title('k匿名化: kと有用性', fontsize=15)
ax2.set_ylim(30, 60)
ax2.grid(True, alpha=0.3)
for x, y in zip(k_values, usefulness):
    ax2.text(x, y + 0.7, f"{y:.1f}", color='#000000', ha='center', fontsize=12)
fig.tight_layout()
fig.savefig('experiments/summary_figures/k_anon_usefulness_vs_k.png', dpi=300)
plt.close(fig)
print('Saved k-anon tradeoff plots')
