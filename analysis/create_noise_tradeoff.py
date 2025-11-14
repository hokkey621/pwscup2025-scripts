#!/usr/bin/env python3
from __future__ import annotations

import matplotlib.pyplot as plt

plt.rcParams['font.family'] = 'Hiragino Sans'

noise_percent = [1, 4, 10]
usefulness = [67.18, 58.48, 51.89]
attack_total = [8897, 7307, 3177]

fig, ax = plt.subplots(figsize=(7.5, 4.5))
ax.plot(noise_percent, usefulness, marker='o', color='#43b0b1')
ax.set_xlabel('ノイズ付与率 (%)', fontsize=13)
ax.set_ylabel('有用性スコア (0–80)', color='#43b0b1', fontsize=13)
ax.tick_params(axis='both', colors='#000000', labelsize=12)
ax.set_title('ノイズ付与: 有用性への影響', fontsize=15)
ax.set_ylim(40, 80)
ax.grid(True, alpha=0.3)
for x, y in zip(noise_percent, usefulness):
    ax.text(x, y + 0.7, f"{y:.1f}", color='#000000', ha='center', fontsize=12)
fig.tight_layout()
fig.savefig('experiments/summary_figures/noise_usefulness_vs_level.png', dpi=300)
plt.close(fig)

fig, ax = plt.subplots(figsize=(7.5, 4.5))
ax.plot(noise_percent, attack_total, marker='o', color='#f04a51')
ax.set_xlabel('ノイズ付与率 (%)', fontsize=13)
ax.set_ylabel('攻撃成功数 (TOTAL)', color='#f04a51', fontsize=13)
ax.tick_params(axis='both', colors='#000000', labelsize=12)
ax.set_title('ノイズ付与: 攻撃成功数への影響', fontsize=15)
ax.set_ylim(0, 10000)
ax.grid(True, alpha=0.3)
for x, y in zip(noise_percent, attack_total):
    ax.text(x, y + 50, f"{y}", color='#000000', ha='center', fontsize=12)
fig.tight_layout()
fig.savefig('experiments/summary_figures/noise_attack_vs_level.png', dpi=300)
plt.close(fig)
print('Saved noise tradeoff plots')
