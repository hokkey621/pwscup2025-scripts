# Template 実験フレーム

Bi→Ci の匿名化手法を素早く試すための最小構成です。テンプレートを別名コピーし、自分の手法ごとに `scripts/anonymize.py` と設定ファイルを調整するだけで、生成〜採点〜記録までを 1 コマンドで回せます。

---

## 0. 前提

- コマンドはリポジトリルートで実行する想定です。
- 依存環境は事前に `uv sync` で構築してください。以降は `uv run ...` で統一します。
- Bi サンプルとしては `data/HI_10K.csv` など配布データを利用します。独自 Bi を使う場合は、フォーマットチェックに通ることを先に確認してください。

---

## 1. ディレクトリ構成

| パス | 役割 |
| --- | --- |
| `config/params.json` | 匿名化パラメータ。列ごとのノイズ幅や入れ替え確率を JSON で管理します。 |
| `scripts/anonymize.py` | Bi を読み込み Ci を生成する共通ユーティリティ。`TemplateAnonymizer` をベースに、必要な処理を編集します。 |
| `scripts/run_experiment.py` | Ci 生成 → `evaluation/eval_all.py` 実行 → ログ／指標保存までを自動化する CLI。 |
| `scripts/run_eval.sh` | 手動で評価だけを行いたい場合の薄いラッパー。 |
| `outputs/ci/` | 生成した Ci を保存するフォルダ。ファイル名に手法・種別を入れると後で追跡しやすくなります。 |
| `outputs/logs/` | 評価コマンドの標準出力・標準エラーをタイムスタンプ付きで保存。 |
| `reports/` | 実験メモや Markdown レポート、集計 JSON などを置く場所。 |

---

## 2. クイックスタート

1. **テンプレートをコピー**
   ```bash
   cp -R template experiments/<method_name>
   ```
2. **パラメータを調整**
   - `config/params.json` で列ごとのノイズ幅・確率を編集。
   - `scripts/anonymize.py` の `TemplateAnonymizer` や補助関数に、手法固有の処理を追加。
3. **実験を実行**（リポジトリルートで実行）
   ```bash
   uv run python experiments/<method_name>/scripts/run_experiment.py \
     --bi data/HI_10K.csv \
     --ci experiments/<method_name>/outputs/ci/HI_<method_name>.csv \
     --config experiments/<method_name>/config/params.json \
     --seed 42 \
     --print-details \
     --metrics-json experiments/<method_name>/reports/metrics.json
   ```
4. **結果を確認**
   - 標準出力に採点結果が表示されます。
   - ログは `outputs/logs/<Ci名>_YYYYMMDD-hhmmss.log` に保存。
   - 指標は `--metrics-json` で指定したファイルへ保存されます。

---

## 3. `run_experiment.py` の主な引数

- `--bi` (必須): 入力となる Bi.csv。
- `--ci` (必須): 生成した Ci の出力パス。
- `--config`: 匿名化パラメータ JSON。省略時はテンプレ内の `config/params.json`。
- `--seed`: 乱数シード。再現したい場合に指定。
- `--print-details`: `evaluation/eval_all.py -d` を付与し、詳細差分を表示。
- `--force`: Ci のフォーマット異常があっても `-f` で採点を強行。
- `--metrics-json`: 評価結果を JSON で書き出すパス。指定しない場合はファイル出力なし。
- `--log-dir`: ログ保存先。デフォルトは `<テンプレート>/outputs/logs`。

---

## 4. 典型的な編集ポイント

- **カテゴリ列の操作**: `mutate_categorical()` の確率を調整、またはカテゴリ別ロジックを追加。
- **連続値のノイズ**: `add_float_noise()` の振れ幅や丸め桁を設定。必要なら独自の変換関数を生やして `TemplateAnonymizer` に組み込み。
- **フラグ列の反転**: `flip_binary()` の確率を変更。複数列を連動させたい場合は個別関数を追加。
- **AGE などのクリップ**: 読み込み時に規格外値があれば `read_bi_dataframe()` 内で自動クリップしています。別ルールにしたい場合はここを編集。

---

## 5. ベストプラクティス

- 実験ごとの作業はテンプレートをコピーしたフォルダ内で完結させ、他フォルダを触らない。
- 生成した Ci とログは削除せずに `outputs/` 配下へ蓄積し、比較しやすくする。
- `reports/` に Markdown で概要・パラメータ・スコアを記録し、後から再現できるようにする。
- `uv sync` はリポジトリ直下で事前に実行しておき、以降は `uv run` で依存ライブラリを共有。

この README を見れば、テンプレートのコピーからスコア記録までの手順が一目で分かる構成になっています。必要に応じて、各手法フォルダでさらに手法固有の README を足してください。
