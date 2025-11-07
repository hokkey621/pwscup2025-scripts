# webapp/AGENT.md

この文書は、Codex などのエージェントが `webapp/` ディレクトリを保守する際のガイドラインをまとめたものです。既存の SecHack365 プロジェクト規約（`AGENTS.md`）を前提に、Web アプリ特有の注意事項を追記します。

## 1. ディレクトリ方針
- **編集対象は `webapp/` 配下のみ。** 仕様上、ルートや `template/` など他ディレクトリの変更は禁止です。
- 一時生成物（Bi′, Ci, モデル、ログ、uv キャッシュ）は `webapp/outputs/` に集約済み。`.gitignore` を維持し、生成物をコミットしないこと。
- 新規モジュールを追加する際は、PEP 8 準拠・ASCII コメントを基本とし、必要な補足のみ日本語コメントを入れる。

## 2. 主要モジュールの役割
| ファイル | 役割 | 補足 |
| --- | --- | --- |
| `__init__.py` | 定数およびパス定義 | `DEFAULT_BI_PATH` などを集中管理。 |
| `app.py` | Streamlit UI 実装 | ペイン構成と `st.session_state` を一元管理。 |
| `anonymize.py` | 入力整形と Ci 生成 | アルゴリズム A/B のロジックとフォーム制御を担当。 |
| `evaluate.py` | 評価スクリプト呼び出し | uv でルート配下の公式スクリプトを順次実行。 |
| `outputs/.gitignore` | 生成物の除外設定 | 必ず維持する。 |

## 3. 実装ルール
- **セッション管理:** Streamlit の状態は `st.session_state` を介して同期し、副作用のある処理はボタン押下時のみ実行する。
- **アルゴリズム追加:** `anonymize.ALGORITHM_OPTIONS` に ID と説明を追加し、`generate_ci` 内で分岐を実装する。バイナリ列変形は評価に影響するため避けること。
- **評価フロー:** `evaluate.run_evaluation` は `util/check_and_fix_csv.py → analysis/xgbt_train.py → attack/attack_example.py → evaluation/check_ans.py → evaluation/eval_all.py` の順で実行する。順序変更は要検討ポイント。
- **サブプロセス:** `uv run` を使用し、`UV_CACHE_DIR` を `webapp/outputs/.uv-cache` に設定する。環境依存エラーが出た場合はキャッシュディレクトリの権限を確認。
- **データ整合性:** Bi′ は `check_and_fix_csv.py` を通すこと。Ci は 10,000 行・列順固定を守る。バイナリ列（ターゲット列など）の値は `0/1` を維持する。

## 4. 推奨テスト手順
1. **コード静的チェック**  
   - `python -m compileall webapp` で構文エラーを確認。  
   - `uv run ruff webapp`（ruff 導入済みの場合）。
2. **CLI シナリオテスト**  
   - `UV_CACHE_DIR=webapp/outputs/.uv-cache uv run python - <<'PY' … PY` で匿名化〜評価を一括実行し、例外なく完走することを確認。  
   - 実行結果の `EvaluationResult` に有効な数値が入っているか確認。
3. **UI 起動確認**  
   - `UV_CACHE_DIR=webapp/outputs/.uv-cache uv run streamlit run webapp/app.py` を起動し、3 ペインのフローが仕様通り動作するかブラウザで確認。

## 5. 変更時のチェックリスト
- [ ] 仕様書（`webapp/instruct.md`）に反しない変更である。  
- [ ] 生成物が `webapp/outputs/` 以外に散在していない。  
- [ ] アルゴリズム追加時は UI ラベルと内部処理が同期している。  
- [ ] エラーハンドリングで `EvaluationError` / `AnonymizationError` のメッセージがユーザーに伝わる形になっている。  
- [ ] 追加依存は極力避け、必須の場合は `pyproject.toml` への追記が必要か検討。  
- [ ] 日本語 UI 文言は丁寧で簡潔になっている。

## 6. トラブル対応メモ
- **uv の Permission Error:** `UV_CACHE_DIR` を書き込み可能なパスに設定する。CI/Sandbox では `webapp/outputs/.uv-cache` を推奨。  
- **評価スクリプトが失敗する:** `outputs/logs/` の最新ログで失敗ステップを確認。Bi′ の Fix を忘れていないか、Ci の行数が 10,000 か、攻撃スクリプトの依存が整っているかをチェック。  
- **Streamlit の状態が更新されない:** ボタン処理内で `st.session_state` を書き換えているか確認し、必要に応じて `st.experimental_rerun()` を使用。

## 7. ドキュメント保守
- ユーザー向け情報は `webapp/README.md` に記載。更新時は両方のファイルを同期する。  
- 仕様書は `webapp/instruct.md` にあるため、改定指示がない限り直接編集しない。

以上を踏まえ、将来の改修でもデモ体験を損なわないよう慎重に対応してください。
