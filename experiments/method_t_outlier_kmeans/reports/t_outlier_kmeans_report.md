# t分布×k-means 外れ値置換レポート

## 手法概要
- 各数値列に対して`t`分布を仮定し、両側で指定割合の外れ値を閾値計算で抽出。
- 抽出した外れ値のみを1次元k-means（最大3クラスタ）に集約し、クラスタ中心で代表値置換。
- 置換後は整数列を丸め、浮動小数は小数2桁にそろえて `CiDataFrame` 仕様を満たす。
- 乱数シードを共有して `k-means` と置換処理の再現性を確保。

## 実験条件
- 入力: `data/HI_10K.csv`（事前に `util/check_and_fix_csv.py` で補正）。
- 出力: `experiments/method_t_outlier_kmeans/outputs/ci/` 以下に3種類のCiを生成。
- 評価: `evaluation/eval_all.py` の通常設定、`analysis/xgbt_train.py` + `attack/attack_example.py` による匿名性評価。
- 置換率は `tail_ratio` を 1%, 5%, 10% に変更し、それ以外のパラメータ（最大クラスタ数3、乱数シードなし）は固定。

## 結果まとめ
| tail_ratio | stats_diff_max_abs | LR(asthma)_diff | KW_IND_diff_max_abs | Ci utility (/80) | Di val acc | Attack TOTAL |
| --- | --- | --- | --- | --- | --- | --- |
| 0.01 | 0.00650 | 0.13700 | 3.39e-05 | 76.999 | 0.8940 | 9437 |
| 0.05 | 0.00817 | 0.09145 | 5.41e-05 | **77.843** | **0.8990** | **9353** |
| 0.10 | 0.01089 | 0.37336 | 1.17e-04 | 72.095 | 0.8960 | 9439 |

## 所見
- 1%設定では外れ値置換が `encounter_count`〜`mean_bmi` の9列に限定され、全指標は安定。ただし攻撃成功件数は 9437 でベースライン比ほぼ横ばい。
- 5%設定では `AGE` や `mean_weight` など追加列にも置換が入り、Ci utility が 77.84 と今回の最高値かつ攻撃成功も 9353 まで減少。LR差分も 0.091 と最小で、実用バランスが最も良い。
- 10%設定では `LR(asthma)` の差分が 0.37 まで増大し、有用性スコアも 72.09 まで低下。外れ値を潰し過ぎると特徴量相関が大きく崩れ、Di 精度・攻撃結果も悪化傾向（TOTAL 9439）となる。
- 以上より、`tail_ratio` は 1〜5%の範囲で列ごとに調整するのが良さそう。特に `mean_weight` や `mean_systolic_bp` のような連続量は5%で十分で、10%では再識別リスクを増やす恐れがある。

## 生成物
- `experiments/method_t_outlier_kmeans/outputs/ci/t_outlier_p00{1,5,10}.csv`
- `experiments/method_t_outlier_kmeans/outputs/model/*.json`
- `experiments/method_t_outlier_kmeans/outputs/attack/*.csv`
- 評価ログ: `experiments/method_t_outlier_kmeans/outputs/logs/`
- メトリクスJSON: `experiments/method_t_outlier_kmeans/reports/t_outlier_p00{1,5,10}_metrics.json`
