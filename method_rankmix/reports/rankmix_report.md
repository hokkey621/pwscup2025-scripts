# RankMix 実験レポート

## 手法概要
- `config/params.json` でカテゴリ入れ替え確率と整数/実数ノイズ幅を設定。
- 連続値(`mean_systolic_bp`, `mean_diastolic_bp`)には RankMix を追加。
  - 値を昇順に並べ、±window 以内の別サンプルを選んで線形補間。
  - 列レンジの 1〜2% を標準偏差とするガウス揺らぎを上乗せ。
- BMI は欠損を周辺分布からサンプリングして再度一部欠損化。
- `method_rankmix/outputs/HI_10K_clamped.csv` を作成し、AGE>110 を 110 にクリップして `evaluation/eval_all.py` の入力 Bi として使用。

## 実行コマンド
```bash
uv run python method_rankmix/scripts/run_experiment.py \
  --bi method_rankmix/outputs/HI_10K_clamped.csv \
  --ci method_rankmix/outputs/ci/HI_rankmix.csv \
  --config method_rankmix/config/params.json \
  --seed 2024 \
  --print-details \
  --metrics-json method_rankmix/reports/metrics_rankmix.json
```
- ログ: `method_rankmix/outputs/logs/HI_rankmix_20251027-121839.log`
- 評価スクリプト: `evaluation/eval_all.py` (変更なし)

## スコア結果
| 指標 | 値 |
| --- | --- |
| `stats_diff max_abs` | 0.1619 |
| `LR_asthma_diff max_abs` | 0.9842 |
| `KW_IND_diff max_abs` | 0.0628 |
| `Ci utility (/80)` | **52.59** |

## 所感
- RankMix により平均や分布の歪みは小さく抑えられたが、`LR_asthma_diff` が 0.98 と大きく、Ci utility は 52.6 に留まった。
- 連続値の窓幅を縮める、もしくは `obesity_flag` などのバイナリ列に別処理を行い、ロジスティック回帰での係数乖離を減らす余地がある。
