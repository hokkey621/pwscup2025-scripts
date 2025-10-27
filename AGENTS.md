# Repository Guidelines

## Project Structure & Module Organization
- `analysis/`: Exploratory analytics and model training scripts such as `stats.py`, `LR_asthma.py`, and `xgbt_train.py`. Use these when deriving new metrics from medical CSVs.
- `evaluation/`: Scoring utilities (for example `eval_all.py`, `stats_diff.py`, `LR_asthma_diff.py`) that replicate the Codabench judging pipeline; mirror this layout when adding new evaluation modules.
- `attack/`: Adversarial and membership-inference tooling including `attack_Ci.py`, `attack_Di.py`, and `make_attack_submission.py`. Outputs should stay under `attack/output/` or a similarly isolated folder.
- `anonymization/`, `util/`: Reusable preprocessing helpers (`check_csv.py`, `check_and_fix_csv.py`) for validating column ranges and formatting.
- `data/`: Reference CSVs and JSON range specifications consumed by both evaluation and analysis scripts; treat these as canonical schema samples.

## Build, Test, and Development Commands
- `uv python install 3.12.11`: Install the managed interpreter compatible with `except*` and other features used in utility modules.
- `uv sync`: Materialize `.venv/` from `pyproject.toml` / `uv.lock`; rerun after editing dependencies.
- `uv run python evaluation/eval_all.py data/HI_10K.csv data/MA_10K.csv`: Run the end-to-end Ci utility score (`-d` for verbose logs, `-f` to force scoring despite minor format issues).
- `uv run python analysis/xgbt_train.py --help`: Inspect training options before fitting new models; companion scripts usually accept similar CLI flags.
- `uv run python util/check_and_fix_csv.py data/HI_10K.csv data/columns_range.json tmp.csv`: Optional pre-check to clamp out-of-range values; remove `tmp.csv` if no fixes are needed.

## Coding Style & Naming Conventions
- Follow PEP 8: four-space indentation, snake_case for functions and variables, and UpperCamelCase only for classes.
- Keep CLI entry points under `if __name__ == "__main__":` and expose pure functions for reuse in notebooks or other scripts.
- Validate input frames early, sort columns where deterministic order matters, and prefer explicit constant lists (e.g., `EXPECTED_COLUMNS`) for schema checks.
- Use `black` (default line length 88) and `ruff` style rules if available; otherwise, align with existing formatting in the touched file.

## Anonymization Experiment Workflow (template/ & method_*/)
- ベースライン実験は `template/` をコピーして新しい手法ディレクトリ（例: `method_rankmix/`）を作成し、フォルダ外のファイルは変更しない。
- `config/params.json` で列ごとのノイズや反転確率を管理し、`scripts/anonymize.py` に必要な処理を実装する。Bi 読み込み時は `read_bi_dataframe()` が値域クリップを行うため、特殊な前処理が必要ならここを拡張する。
- 実験実行はリポジトリルートで `uv run python <method>/scripts/run_experiment.py --bi <Bi> --ci <out_Ci> --config <params.json> --seed <seed> --print-details --metrics-json <reports/metrics.json>` を使用し、ログは `<method>/outputs/logs/`、スコアは `<method>/reports/` に保存する。
- 評価は `evaluation/eval_all.py` に依存するため、Bi/Ci の列名・値域が一致しない場合は `util/check_and_fix_csv.py` や `read_bi_dataframe()` のクリップ処理で事前に整形する。
- 実験レポートは `<method>/reports/*.md` に Markdown でまとめ、生成した Ci は `<method>/outputs/ci/` に残して比較可能な状態を保つ。

## Testing Guidelines
- No formal test suite exists; rely on deterministic script runs using sample files (`data/HI_10K.csv`, `data/MA_10K.csv`) and check that metrics stay within expected ranges.
- Invoke helper functions like `eval_diff_max_abs` directly during development to compare DataFrames without writing intermediate CSVs.
- When introducing randomness, expose `--random-state` options and document default seeds to preserve reproducibility.
- Capture noteworthy outputs (scores, warning messages) in commit notes or PR descriptions for traceability.

## Commit & Pull Request Guidelines
- Craft imperative commit titles (`Add evaluation sanity check`, `Fix attack submission path`) and keep the first line under 72 characters.
- Link related issues or Codabench tickets in the message body and summarize metric deltas or formatted files touched.
- Pull requests should include: problem statement, summary of changes, verification steps with concrete commands, and any follow-up tasks.
- Request review when CI-equivalent commands (`eval_all.py`, critical analysis scripts) succeed locally; attach artifacts only when essential.

## Security & Configuration Tips
- Never commit real participant data; sanitize or synthesize minimal examples before sharing.
- Run `python3 util/check_csv.py <file>` prior to uploading datasets to ensure column ranges remain within the published thresholds.
- Store Codabench credentials outside the repository and document sensitive environment variables in private channels, not in version control.
- When distributing trained models, include metadata (`attributes.feature_names`, `xgboost_version`) so validators like `validate_model_json.py` remain effective across environments.
