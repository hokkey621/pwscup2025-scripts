# Raspberry Pi 2台構成メモ

Codex は本メモを基に、SecHack365 医療AI匿名化デモ Web アプリをラズベリーパイ 2 台で実装してください。

## ハードウェア構成
- **ラズパイ1**: Raspberry Pi 5 / 8GB RAM。Streamlit フロントと匿名化処理 (`webapp/app.py`, `webapp/anonymize.py`) を担当し、ブラウザ表示を含む UI レイヤーを一元管理する。
- **ラズパイ2**: Raspberry Pi 4 / 4GB RAM。原則として評価系（有用性スコア算出や機械学習推論）を担当するが、デモ環境ではラズパイ1単体での実行も許可するフェイルオーバー構成とする。

## ディレクトリとファイルの扱い
- 両端末ともリポジトリ直下の `webapp/` 以外は変更しない。テンプレートや root 直下のファイルへ手を入れないこと。
- 評価や一時生成物はすべて `webapp/outputs/` 以下（`bi_prime.csv`, `ci_result.csv`, `model/`, `attack/`, `metrics/`, `logs/`, `.uv-cache/`）に集約する。
- `.gitignore` で除外済みのため、成果物はコミットしない。

## ソフトウェア要件
- Python 3.12 系、仮想環境は `uv` を使用する。
- 依存関係はリポジトリの `pyproject.toml` / `uv.lock` に従い、両ラズパイで `uv sync` を実行する。
- `data/` 直下に公式サンプル `HI_10K.csv`, `HI_100K.csv`, `HI_ans.csv`, `columns_range.json` を配置しておく。

## 運用フロー
1. ラズパイ1で `UV_CACHE_DIR=webapp/outputs/.uv-cache uv run streamlit run webapp/app.py` を起動し、カルテ入力ビューからBiエントリを作成。
2. ボタン `[ 1. 匿名化実行 ]` もしくは `[ 1. 全手法で匿名化 ]` を押すと `anonymize.run_anonymization` が呼ばれ、`RunRecord` が `st.session_state.run_history` に追加される。
3. 匿名化処理完了後、ラズパイ1は `webapp/outputs/bi_prime.csv` と `ci_result.csv` を最新状態に書き出す。Runタブで差分と実行履歴を確認。
4. 有用性スコア確認フロー：
   - **理想ケース**: ラズパイ1が `webapp/outputs/` ディレクトリをネットワーク共有/rsync でラズパイ2へ転送し、ラズパイ2上で `evaluate.run_evaluation` を実行して有用性スコアと機械学習モデル推論（`analysis/xgbt_train.py` の検証精度等）を算出する。
   - **デモ/フォールバック**: 性能やネットワーク制約でラズパイ2を使用できない場合、ラズパイ1が `evaluate.run_evaluation` をローカル実行し、UIへ即時反映する。
5. 評価結果 (`EvaluationResult`) はラズパイ1の `st.session_state.run_history` の `eval_result` に格納され、指標メトリクスとログが画面へ反映される。
6. すべてのログは `webapp/outputs/logs/` に保存し、トラブルシュート時に参照する。

## 設計方針
### 役割分担
- **ラズパイ1 (Pi5/8GB)**  
  - Streamlit UI、フォーム入力、`anonymize.py` によるBi′/Ci生成。  
  - 匿名化結果と最新Run状態を常時保持し、ユーザー操作とセッション管理を行う。  
  - 有用性スコア要求時にラズパイ2へ処理依頼を送信するオーケストレーター。
- **ラズパイ2 (Pi4/4GB)**  
  - `evaluate.py` の全ステップを担当（CSV整形、学習、攻撃、評価）。  
  - 処理完了後に評価メトリクスとログを返却。  
  - 処理が重い場合はキューイングして順次実行する。  
  - デモモードではラズパイ1に同処理を委譲できるようにする。

### 処理シーケンス
1. ラズパイ1: 入力 → 匿名化 (`run_anonymization`) → `RunRecord` 更新。  
2. ユーザーが「有用性スコア確認」(= `[ 2. スコア計算実行 ]`) を押下。  
3. ラズパイ1: Bi′/Ci を `webapp/outputs/` に保存し、評価ジョブ要求を作成。  
4. ラズパイ2: ファイルを受領後 `evaluate.run_evaluation` を実行し、`EvaluationResult` を JSON などで返却。  
5. ラズパイ1: 受領結果を該当 `RunRecord.eval_result` に格納し UI 更新。  
6. フォールバック時は 3→4→5 を同一ノードで完結させる。

### データ連携
- ラズパイ1・ラズパイ2・MacBook を **同一 L2 スイッチに有線接続**し、固定IPまたは DHCP 予約でアドレスを管理する。  
- デモ時は MacBook から両ラズパイへ SSH 接続し、状態確認や手動リトライを行う。  
- 軽量な JSON RPC / REST を想定し、`webapp/outputs` のCSVパス or データ本体を送信する。  
- 最小構成では `rsync` + SSH でファイル同期 → ラズパイ2側で CLI 実行 → 結果 JSON を `scp` で返す手順を推奨。

### SSH 設定（例）
macOS の `~/.ssh/config` に以下が登録済みで、**Pi5(ラズパイ1)は `rp3`、Pi4(ラズパイ2)は `rp1`** に対応する。

```
# Raspberry Pi
Host rp1
    HostName rp1.local
    User raspi1
    Port 22

Host rp2
    HostName rp2.local
    User raspi2
    Port 22

Host rp3
    HostName rp3.local
    User raspi3
    Port 22
```

- `rp3` = ラズパイ1 (Pi5/8GB, IP 169.254.37.105)、`rp1` = ラズパイ2 (Pi4/4GB, IP 169.254.146.11)。`ssh rp3` / `ssh rp1` ですぐ接続できる前提。  
- Bonjour/mDNS が使えない環境に備え、L2 スイッチのDHCPリストからIPを把握し `/etc/hosts` や `~/.ssh/config` に追記しておくと安心。

## 実装計画
1. **通信レイヤー整備**  
   - `raspi_deploy/config.py`（仮）などでラズパイ2のアドレス/ユーザー/転送方法を設定。  
   - `evaluate.run_evaluation` 呼出し前に「ローカル/リモート」モードを切り替えるラッパー関数を実装。
2. **ジョブ依頼API**  
   - シンプルに SSH 経由で `uv run python -m webapp.raspi_worker evaluate --bi ...` を叩くスクリプトを用意。  
   - 成功時に `EvaluationResult` を JSON ファイルで返すよう `evaluate.py` を拡張（標準出力 JSON 化 or 既存 `latest.json` を再利用）。
3. **Streamlit連携**  
   - `[ 2. スコア計算実行 ]` ボタン押下時に上記ラッパーを呼び、完了待ちスピナーを表示。  
   - フォールバック条件（ネットワーク未設定/タイムアウト）を検知し、自動でラズパイ1ローカル実行へ切り替える。
4. **ログ/監視**  
   - ラズパイ2実行ログを `webapp/outputs/logs/remote/` に転送し、UIの `st.expander` にも表示。  
   - 失敗時には UI で明示し、再実行ボタンを提示。
5. **検証**  
   - 片側のみの構成で CLI テスト → 2台構成でファイル転送・評価実行 → Streamlit UI で end-to-end 確認。  
   - サンプルデータ（`HI_10K.csv`）で latency/CPU 負荷を計測。

## 画面仕様（webapp 既存仕様の要約）
### カルテ入力ビュー
- セクション構成: ①基本プロフィール（GENDER, AGE, RACE, ETHNICITY）、②受診歴／処置サマリ（encounter_count など6列）、③既往歴フラグ（asthma/stroke/obesity/depression）、④バイタルサイン（mean_systolic_bp 等4列）、⑤その他（埋め切れなかった列）。
- 数値列は `st.number_input`（int/floatで範囲設定）、バイナリ列は `st.toggle`、カテゴリ列は `st.selectbox`、残りは `st.text_input`。
- アルゴリズム選択 `st.radio` ：
  - `naive` = アルゴリズムA (ナイーブ加工: Bi′コピー)
  - `main` = アルゴリズムB (非バイナリ数値列へノイズ付与)
  - `k_anonymity` = アルゴリズムC (k=2 のマイクロアグリゲーション; `experiments/method_k_anonymity_k02` の最良設定)
  - `t_outlier_kmeans` = アルゴリズムD (t分布で外れ値抽出→k-means置換; tail_ratio=0.05, max_clusters=3)
- 実行ボタン:
  - `[ 1. 匿名化実行 ]`（選択アルゴリズムのみ）
  - `[ 1. 全手法で匿名化 ]`（登録済み全アルゴリズムを一括実行）
- `入力を初期値に戻す` で代表値へリセット。

### 匿名化結果ビュー
- Run タブごとに差分と評価を表示。タブ見出しは `Run {id}: {アルゴリズム名}`。
- 差分表示 (`render_ci_panel`):
  - Bi′ と Ci の新規行（`new_index`）を比較し、`Bi'`, `Ci`, `差分` を表形式で表示。
  - 変更列は背景ハイライト、`st.metric` で `変更列数 / 総列数` を提示。
- 評価表示 (`render_evaluation_panel`):
  - `[ 2. スコア計算実行 ]` ボタンで `evaluate.run_evaluation` をキック。
  - 指標: 有用性スコア (U = 1 - Δloss)、匿名性スコア (P = 1 - A)、Di検証精度、攻撃成功件数／MIAメッセージ。
  - ログを `st.expander("評価ログ ...")` に格納。
- 画面上部に `[ 2. 全手法の評価を実行 ]` ボタンを配置し、Run 全体を一括評価。成功後は `st.rerun()` で再描画。
- 指標解説ブロックに `U`, `P`, `Acc_Di`, MIA説明を記載し、Runごとのサマリ表を `st.table` で表示。

## 参考コマンド
```bash
# 依存関係
uv python install 3.12.11
uv sync

# Streamlit 起動（ラズパイ1）
UV_CACHE_DIR=webapp/outputs/.uv-cache \
uv run streamlit run webapp/app.py

# CLI テスト（任意の端末）
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

## リモート評価設定手順
1. Pi5 側の `webapp/` 直下で `cp webapp/raspi-config.example.json webapp/raspi-config.json` を実行し、以下を編集します。
   - `host`, `user`, `repo_path`: Pi4 の SSH 接続情報とリポジトリパス
   - `identity_file`, `ssh_common_args`: 任意の鍵ファイルや SSH オプション
   - `remote_cache_dir`, `jobs_dir`: Pi4 上で `uv run` が使用するキャッシュ／ジョブ格納先
2. Pi4 では `uv sync` 済みのリポジトリを `repo_path` に配置し、`webapp/remote_jobs/` ディレクトリを作成しておきます。
3. Pi5 上で Streamlit から評価ボタンを押すと、`webapp/evaluate.py` が `bi_prime.csv` / `ci_result.csv` をコピーし、以下を自動実行します。
   ```bash
   ssh <user>@<host> "cd <repo_path> && UV_CACHE_DIR=<...> uv run python -m webapp.raspi_worker --inputs webapp/remote_jobs/<job>/inputs --outputs webapp/remote_jobs/<job>/outputs"
   ```
4. `webapp/raspi_worker.py` は Pi4 上で評価を完了させ、JSON ログを `outputs` ディレクトリへ書き出します。Pi5 が JSON を取得して `EvaluationResult` に復元し、Streamlit に即時反映します。
5. `webapp/raspi-config.json` を削除する、または `mode` を `local` に戻すと Pi5 単体実行に切り替わります。

## 注意事項
- `UV_CACHE_DIR` は常に `webapp/outputs/.uv-cache` を指定し、書き込み権限エラーを防止する。
- 評価失敗時はラズパイ2側の `webapp/outputs/logs/` と MIA 生成物を確認し、Bi′/Ci が 10,000 行・列順一致か、`check_and_fix_csv.py` が正常終了しているかをチェックする。
- 追加アルゴリズムを導入する場合は `anonymize.ALGORITHM_OPTIONS` と `generate_ci` を拡張し、全手法ボタンとの整合性をとる。
