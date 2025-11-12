# ノイズ量別匿名化実験サマリ

## 実験条件
- Bi: `data/HI_10K.csv`
- 共通乱数シード: `2025`
- `experiments/noise_lvl*/scripts/ano.py` は `config/params.json` を読み込み、カテゴリ入替・フラグ反転・整数/浮動小数ノイズを列グループごとに付与
- `run_experiment.py --print-details --metrics-json` で Ci 生成 → フォーマット検証 → Di 学習 → 攻撃評価 → `evaluation/eval_all.py`

## ノイズ設定とスコア
| Experiment | cat swap prob | flag flip prob | age span | int scale | float scale | stats_diff max abs | LR(asthma) diff | KW diff | Ci utility (80点満点) |
|-----------|---------------|----------------|----------|-----------|-------------|--------------------|-----------------|---------|-----------------------|
| noise_lvl1_soft | 0.01 | 0.01 | 1 | 0.3 | 0.3 | 0.0321 | 0.5573 | 0.0197 | 67.18 |
| noise_lvl2_mild | 0.02 | 0.02 | 2 | 0.6 | 0.7 | 0.0690 | 0.8516 | 0.0326 | 59.56 |
| noise_lvl3_balanced | 0.04 | 0.04 | 3 | 1.0 | 1.0 | 0.1008 | 0.8180 | 0.0562 | 58.48 |
| noise_lvl4_strong | 0.07 | 0.07 | 4 | 1.5 | 1.6 | 0.1354 | 0.8200 | 0.1070 | 56.04 |
| noise_lvl5_extreme | 0.10 | 0.10 | 6 | 2.2 | 2.4 | 0.1846 | 0.8702 | 0.1662 | 51.89 |

## 観察メモ
- **有用性**: ノイズ量を増やすほど `ci_utility` が連続的に低下し、極端設定では 51.9/80 まで下がった。
- **匿名性指標**: `stats_diff_max_abs` や `kw_ind_max_abs` はノイズに比例して増加し、データ間距離が広がっている。
- **LR(asthma) diff**: 中程度までは 0.82 前後で推移し、極端設定では 0.87 まで上昇。`noise_lvl3_balanced` 付近が匿名性・有用性の両立点として扱いやすい。
- **Di モデル精度**: `analysis/xgbt_train.py` の Validation Accuracy は Soft=0.875 → Extreme=0.765 まで低下し、ノイズ増加で攻撃成功余地は小さくなる一方で予測性能も落ちる傾向。

## 出力物
- Ci CSV: `experiments/noise_lvl*/outputs/ci/ci_noise_*.csv`
- 評価ログ: `experiments/noise_lvl*/outputs/logs/`
- モデル/攻撃結果: `experiments/noise_lvl*/outputs/model`, `experiments/noise_lvl*/outputs/attack`
- メトリクス JSON: `experiments/noise_lvl*/reports/metrics.json`
