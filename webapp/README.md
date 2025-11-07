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
画面は `st.columns(3)` で 3 ペインに分割され、左から順に操作します。

1. **ペイン1：模擬電子カルテ（入力側）**  
   - Bi スキーマ準拠のフォームを自動生成します。代表値で初期化されるため、特異な値（例：年齢 99 歳）を入力しやすい構成です。  
   - ラジオボタンで匿名化アルゴリズムを選択します。  
     - アルゴリズムA：そのままコピー（ナイーブ加工）  
     - アルゴリズムB：ノイズ注入（本命加工）  
   - `[ 1. 匿名化実行 ]` を押すと Bi′（行数 10,000 を維持）と Ci を生成し、セッションに保存します。

2. **ペイン2：匿名化データ（Ci）ビュー**  
   - 直近の Ci 末尾 5 行、および新規行の Bi′ / Ci を並べて表示します。  
   - アルゴリズム切り替えにより、ビフォー・アフターを即座に比較できます。

3. **ペイン3：PWS CUP 2025 評価ビュー**  
   - `[ 2. スコア計算実行 ]` を押すと、以下の処理を順次実行して結果を表示します。  
     1. `util/check_and_fix_csv.py` による Bi′ の補正  
     2. `analysis/xgbt_train.py`（Di 学習、検証精度取得）  
     3. `attack/attack_example.py`（Ai を用いた MIA 攻撃）  
     4. `evaluation/check_ans.py`（攻撃結果の照合）  
     5. `evaluation/eval_all.py`（有用性指標の計算）  
   - 指標は `st.metric` で表示され、攻撃成功件数に応じてステータス表示（Success / Warning）が切り替わります。  
   - 各サブプロセスの標準出力は「評価ログ」にまとめて参照できます。

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
  → `evaluation` ペインのログで `check_and_fix_csv.py` の完了を確認し、問題が残る場合は入力値を見直してください。
- **攻撃成功件数が極端に大きい / 小さい**  
  → 本アプリはデモ用であり、スコアそのものより「処理が動く」ことを重視しています。説明時にはこの前提を共有してください。

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
