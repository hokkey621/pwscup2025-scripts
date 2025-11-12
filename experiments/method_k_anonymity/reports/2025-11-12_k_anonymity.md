# k匿名化実験メモ (2025-11-12)

## 実装概要
- `experiments/method_k_anonymity/scripts/ano.py` に k=10 のマイクロアグリゲーションを実装。
- Bi 行を乱数シャッフル → k 件ずつのブロックを作成し、端数は直前ブロックへ吸収して必ず `>=k` を保証。
- 各ブロック内で列仕様 (`CiDataFrame.COL_SPECS`) に基づき代表値を算出。
  - 数値列: 平均→min/maxクランプ→指定小数桁で丸め。
  - カテゴリ列: 最頻値（同票は辞書順）を選択。
  - 日付列: 中央付近を選ぶ汎用処理を用意（今回列は無し）。
- 代表値をブロック全行へ展開し、`CiDataFrame` で最終フォーマットを担保。

## 実験条件
- 入力 Bi: `data/HI_10K.csv`
- 出力 Ci: `experiments/method_k_anonymity/outputs/ci/k_anon.csv`
- 実行コマンド:
  ```sh
  uv run python experiments/method_k_anonymity/scripts/run_experiment.py \
    --bi data/HI_10K.csv \
    --ci experiments/method_k_anonymity/outputs/ci/k_anon.csv \
    --metrics-json experiments/method_k_anonymity/reports/metrics.json \
    --log-dir experiments/method_k_anonymity/outputs/logs \
    --print-details
  ```
- ログ: `experiments/method_k_anonymity/outputs/logs/k_anon_20251112-215853.log`

## 指標 (metrics.json)
| 指標 | 値 |
| --- | --- |
| stats_diff_max_abs | 0.3665 |
| lr_asthma_max_abs | 1.0000 |
| kw_ind_max_abs | 0.2808 |
| ci_utility | 39.72 / 80 |

## 所感
- k=10 で全列を代表値化した結果、平均的な統計差分は中程度に抑えられたが、`lr_asthma_diff` が最大値 (1.0) となり、Di に対する影響が大きい。
- 数値列を単純平均で潰すと、稀な値を含む列で情報が失われ utility スコアが低下する傾向。列ごとに一般化レンジを変える、もしくは機微列のみ k 匿名化し残りはノイズ追加などのハイブリッドが必要。
- まずは `k` の調整や列選択を変えたバリエーションを追加し、`lr_asthma_diff` を 0.3 未満へ下げる施策が必要。
