# Template 実験フレーム

Bi→Ci の匿名化手法を素早く試すための最小構成です。テンプレートを別名コピーし、`scripts/ano.py` に自分の加工ロジックを書いてから 1 コマンドで Ci 生成・チェック・評価まで実行できます。

---

## 0. 前提

- コマンドはリポジトリルートで実行する想定です。
- 依存環境は事前に `uv sync` で構築してください。以降は `uv run ...` で統一します。
- サンプル Bi は `data/HI_10K.csv` を想定しています。独自 Bi を使う場合も `util/check_csv.py` に通ることを先に確認してください。

---

## 1. ディレクトリ構成

| パス | 役割 |
| --- | --- |
| `scripts/ano.py` | Bi→Ci 変換ロジックを記述するファイル。`generate_ci()` を編集して独自手法を実装します。 |
| `scripts/run_experiment.py` | `ano.py` を呼び出し、Ci 生成→フォーマット確認→有用性評価に加え、Di 学習と攻撃評価までを一括実行する CLI。 |
| `scripts/run_eval.sh` | Ci が既に存在する場合に評価だけを再実行したいときの薄いラッパー。 |
| `outputs/ci/` | 生成した Ci を保存するフォルダ。ファイル名に手法や日付を入れると追跡しやすくなります。 |
| `outputs/logs/` | 評価コマンドの標準出力・標準エラーをタイムスタンプ付きで保存。 |
| `outputs/model/` | Di（学習済みモデル）を保存。匿名性評価の攻撃スクリプトが参照します。 |
| `outputs/attack/` | 攻撃結果CSVを保存。`check_ans.py` による匿名性評価で利用します。 |
| `reports/` | 実験メモやスコア集計、Markdown レポートなどを置く場所。 |

---

## 2. クイックスタート

1. **テンプレートをコピー**
   ```bash
   cp -R template experiments/<method_name>
   ```
2. **匿名化処理を実装**
   - `experiments/<method_name>/scripts/ano.py` の `generate_ci(df_bi: pd.DataFrame)` を編集し、Bi から Ci を生成する処理を書く。
   - 必要に応じて補助関数を追加して構いません。
3. **ワンコマンドで実験実行**（リポジトリルートで実行）
   ```bash
   uv run python experiments/<method_name>/scripts/run_experiment.py \
     --bi data/HI_10K.csv \
     --ci experiments/<method_name>/outputs/ci/<method_name>.csv \
     --metrics-json experiments/<method_name>/reports/metrics.json \
     --print-details
   ```
   - デフォルト値に任せる場合は引数なしでも実行できます。
   - タイピングを省きたい場合は以下のシェルスクリプトも利用できます。
     ```bash
     template/scripts/run_method.sh experiments/<method_name>
     ```
     追加オプションを渡したい場合は末尾に付け足してください（例: `--skip-check`）。
   - 匿名性評価をスキップしたい場合は `--skip-privacy` を指定してください。
4. **結果を確認**
   - チェック結果・有用性スコアのサマリ・匿名性評価（Di 学習精度、攻撃成功数など）が標準出力に表示されます。
   - ログは `outputs/logs/<Ci名>_YYYYMMDD-hhmmss.log` に保存され、学習・攻撃ログも同一ファイルにまとまります。
   - `outputs/model/` に学習済み Di、`outputs/attack/` に攻撃結果CSVが書き出されます。
   - `--metrics-json` を指定した場合、パース済みスコアが JSON として書き出されます。

---

## 3. `run_experiment.py` の主な引数

- `--bi`: 入力 Bi.csv。既定は `data/HI_10K.csv`。
- `--ci`: 出力 Ci.csv。既定は `template/outputs/ci/ci_output.csv`。
- `--seed`: `ano.py` に渡す乱数シード。省略時は固定しません。
- `--range-json`: `util/check_csv.py` に渡す列仕様。既定は `data/columns_range.json`。
- `--skip-check`: 値域チェックをスキップしたい場合に指定。
- `--no-fix-bi`: Bi に含まれる範囲外値を `util/check_and_fix_csv.py` で補正せず、そのまま使用する。
- `--ai`: 匿名性評価で使用する Ai.csv。既定は `data/HI_100K.csv`。
- `--ans`: `evaluation/check_ans.py` に渡す正解CSV。既定は `data/HI_ans.csv`。
- `--model-json`: Di モデルの保存先。省略時は `outputs/model/<Ci名>.json`。
- `--attack-output`: 攻撃結果CSVの保存先。省略時は `outputs/attack/<Ci名>_attack.csv`。
- `--train-target`: Di 学習で用いるターゲット列。既定は `stroke_flag`。
- `--skip-privacy`: Di 学習・攻撃評価をスキップしたい場合に指定。
- `--print-details`: 評価時に `-d` を付与し、詳細差分を表示。
- `--force`: 評価時に `-f` を付与し、軽微なフォーマット警告を無視して続行。
- `--metrics-json`: パース済みスコアを JSON へ保存。
- `--log-dir`: ログの保存先。既定は `template/outputs/logs`。

---

## 4. `scripts/ano.py` 編集時のヒント

- デフォルトでは `util/check_and_fix_csv.py` によって補正済みの Bi を `pd.read_csv()` で受け取ります。`--no-fix-bi` を指定した場合は元 Bi をそのまま読み込みます。
- `seed_everything()` を利用すれば NumPy / random のシードをまとめて固定できます。
- 返り値は `CiDataFrame` で書き出せる DataFrame を想定しています。列の追加削除を行う場合は仕様との整合に注意してください。
- 初期状態では単純コピーを返すだけになっているため、必ず処理を上書きしてください。

---

## 5. ベストプラクティス

- 実験ごとはテンプレートをコピーしたフォルダ内で完結させ、他フォルダを直接編集しない。
- 生成した Ci とログを `outputs/` に残しておき、日付や手法名を含めたファイル名で管理する。
- `reports/` に Markdown でパラメータ・スコア・メモを残すと、再現性と比較が容易になります。
- 乱数を使う場合は `--seed` か `seed_everything()` で再現性を担保しておくと便利です。

この README をベースに、各手法フォルダで詳細な説明や追加スクリプトを整備してください。
