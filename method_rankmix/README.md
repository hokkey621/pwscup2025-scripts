# RankMix Anonymous Experiment

テンプレートをコピーして、血圧や BMI といった連続値に「順位近傍の値を混ぜる」RankMix 処理を入れた手法です。カテゴリ列は低確率で入れ替え、フラグ列は反転確率を抑えています。最終的に `evaluation/eval_all.py` でユーティリティを確認します。

## ホールドアウト済み構成
- `config/params.json` : ノイズ幅と RankMix の窓幅を定義。
- `scripts/anonymize.py` : RankMixAnonymizer を実装。
- `scripts/run_experiment.py` : Ci 生成→採点→ログ保存までを自動実行。
- `outputs/ci/` : 生成済み Ci（`HI_rankmix.csv` など）。
- `outputs/logs/` : 採点ログ。
- `reports/` : 実験レポートを配置。

## 実行
```bash
uv run python method_rankmix/scripts/run_experiment.py \
  --bi data/HI_10K.csv \
  --ci method_rankmix/outputs/ci/HI_rankmix.csv \
  --config method_rankmix/config/params.json \
  --seed 2024 \
  --print-details \
  --metrics-json method_rankmix/reports/metrics_rankmix.json
```

`reports/` 配下の Markdown に手法概要とスコアを記録しています。
