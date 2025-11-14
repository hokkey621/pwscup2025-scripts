# SecHack365 医療AI匿名化デモ Web アプリ

本ディレクトリは、SecHack365 対面会でのデモンストレーションを目的とした Streamlit 製 MVP を収めています。医師が入力した 1 行の医療データ Bi を即時に匿名化（Ci 生成）し、PWS CUP 2025 の評価結果をその場で可視化します。

## 前提環境
- Python 3.12 系（リポジトリは `uv` を前提）
- ルート直下の `data/` に PWS CUP 2025 公式サンプル（`HI_10K.csv`, `HI_100K.csv`, `HI_ans.csv`）が存在すること
- 依存パッケージはリポジトリの `pyproject.toml` / `uv.lock` に定義

### セットアップ
```bash
uv python install 3.12.11   # 必要な場合のみ
uv sync                     # 依存パッケージの取得
```

## 起動方法
```bash
UV_CACHE_DIR=webapp/outputs/.uv-cache \
uv run streamlit run webapp/app.py
```

- `UV_CACHE_DIR` を `webapp/outputs/.uv-cache` に明示すると、sandbox 環境でもキャッシュ書き込み権限エラーを回避できます。
- アプリを終了する際は、実行中のターミナルで `Ctrl+C` を押してください。

## 画面構成と手順
アプリは「カルテ入力」「匿名化結果」の 2 画面をボタンで切り替える構成です。

### 1. カルテ入力ビュー
- 実際の電子カルテ風に「プロフィール / 受診歴 / 既往歴 / バイタル / その他」のセクションに分割して入力します。
- アルゴリズム選択 `st.radio`
  - アルゴリズムA：そのままコピー（ナイーブ加工）
  - アルゴリズムB：ノイズ注入（本命加工）
  - アルゴリズムC：k匿名化（k=2。`experiments/method_k_anonymity_k02` で最良だった設定）
  - アルゴリズムD：t分布×k-means 外れ値置換（tail_ratio=0.05, max_clusters=3）
- 実行ボタン
  - `[ 1. 匿名化実行 ]` … 選択中のアルゴリズムのみ走らせる
  - `[ 1. 全手法で匿名化 ]` … 登録済み全アルゴリズムを一括実行し、Run履歴として保存
- `入力を初期値に戻す` でフォームを代表値に戻せます。

### 2. 匿名化結果ビュー
- これまでの実行履歴がタブとして並び、タブごとに匿名化の差分／評価結果を確認できます。
- 差分表示
  - Bi′ と Ci の新規行のみを一覧化し、変更された列は背景色で強調表示。
  - 変更列数 / 総列数を `st.metric` で表示してインパクトを把握できます。
- 評価
  - 各タブに `[ 2. スコア計算実行 ]` を配置。Run単位で `evaluate.py` を実行可能。
  - 画面上部の `[ 2. 全手法の評価を実行 ]` を押すと履歴全体を連続評価し、結果をまとめて更新します。
  - タブ末尾には評価指標の説明（数式付き）と、そのRunのサマリ表を表示しています。
- 評価ログ
  - 各Runのログは `st.expander("評価ログ ...")` にまとめてあり、失敗時のトラブルシュートに活用できます。

## 出力ファイル
評価に伴って生成される成果物はすべて `webapp/outputs/` 以下に保存されます。

| パス | 内容 |
| --- | --- |
| `webapp/outputs/bi_prime.csv` | 直近の Bi′ CSV |
| `webapp/outputs/bi_prime_fixed.csv` | `check_and_fix_csv.py` 適用後の Bi′ |
| `webapp/outputs/ci_result.csv` | 直近の Ci CSV |
| `webapp/outputs/model/di_model.json` | XGBoost Di モデル |
| `webapp/outputs/attack/attack_result.csv` | MIA 攻撃結果 |
| `webapp/outputs/metrics/latest.json` | 直近評価メトリクス（JSON） |
| `webapp/outputs/logs/` | 評価時に生成されたログ（時刻付き） |
| `webapp/outputs/.uv-cache/` | uv のローカルキャッシュ（推奨設定） |

`.gitignore` で隠蔽済みのため、リポジトリにコミットされません。

## よくあるトラブルと対処
- **uv 実行時にキャッシュ書き込みエラーが出る**  
  → `UV_CACHE_DIR=webapp/outputs/.uv-cache` を必ず指定してください。
- **Bi/Ci のフォーマットエラー**  
  → 結果ビューの「評価ログ」で `check_and_fix_csv.py` 実行結果を確認し、問題があればフォーム入力を見直してください。
- **評価スコアが `N/A` のまま**  
  → Runタブで `[ 2. スコア計算実行 ]` を押すか、一括評価ボタンを使用してください。攻撃スクリプトが失敗していないかログを参照します。
- **攻撃成功件数が極端に大きい / 小さい**  
  → 本アプリはデモ用です。スコアより「フローが回ること」を重視している旨を利用者に伝えてください。

## Raspberry Pi 2台構成で評価をオフロードする
- `webapp/raspi-config.example.json` をコピーして `webapp/raspi-config.json` を作成し、Pi4 (評価専用) の `host`, `user`, `repo_path`, `uv_bin`, `remote_cache_dir` などを記入します。`ssh_common_args` や `identity_file` で鍵や `StrictHostKeyChecking` の設定も可能です。
- Pi4 には本リポジトリを同じパスに配置し、`uv sync` 済みであることを前提とします。Pi5 から評価を実行すると `webapp/evaluate.py` が自動で `bi_prime.csv` / `ci_result.csv` を SCP で転送し、`uv run python -m webapp.raspi_worker ...` をリモート実行してスコアを取得します。
- `webapp/raspi_worker.py` は受け取った CSV から `run_evaluation(..., mode="local")` を呼び出し、結果 JSON を `webapp/remote_jobs/<job_id>/outputs/` に書き出します。Pi5 側では JSON/ログを取得して Streamlit に反映し、`webapp/outputs/metrics/latest.json` も更新します。
- `raspi-config.json` を削除するか `mode` を `local` に変更すると、従来通り Pi5 上で評価が実行されます。

## 参考コマンド
- 事前検証として CLI から匿名化〜評価を一括で実行する場合:
  ```bash
  UV_CACHE_DIR=webapp/outputs/.uv-cache \
  uv run python - <<'PY'
  from webapp import anonymize, evaluate

  base = anonymize.load_base_bi()
  profiles = anonymize.build_column_profiles(base)
  entry = anonymize.default_form_values(profiles)
  entry["AGE"] = 99

  result = anonymize.run_anonymization(base, profiles, entry, "main")
  evaluation = evaluate.run_evaluation(result.bi_prime, result.ci)
  print(evaluation)
  PY
  ```

## ライセンス
本アプリはリポジトリのライセンスに従います。詳細はルートのライセンスファイルを参照してください。
