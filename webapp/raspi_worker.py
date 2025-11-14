"""Raspberry Pi 2台構成で評価処理を担当するCLIワーカー。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from .evaluate import (
    BI_OUTPUT_PATH,
    CI_OUTPUT_PATH,
    EvaluationError,
    run_evaluation,
)


def _load_inputs(inputs_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    bi_path = inputs_dir / BI_OUTPUT_PATH.name
    ci_path = inputs_dir / CI_OUTPUT_PATH.name
    if not bi_path.exists() or not ci_path.exists():
        raise EvaluationError(
            f"raspi_worker: 入力CSVが見つかりません (Bi: {bi_path}, Ci: {ci_path})"
        )
    bi_df = pd.read_csv(bi_path)
    ci_df = pd.read_csv(ci_path)
    return bi_df, ci_df


def _save_result(output_dir: Path, filename: str, payload: dict[str, object]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / filename
    result_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return result_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Raspberry Pi 評価ワーカー")
    parser.add_argument("--inputs", required=True, help="Bi/Ci を配置したディレクトリ (リポジトリ相対)" )
    parser.add_argument("--outputs", required=True, help="評価結果JSONを書き出すディレクトリ (リポジトリ相対)" )
    parser.add_argument("--result-name", default="result.json", help="出力する結果ファイル名")
    args = parser.parse_args()

    inputs_dir = Path(args.inputs)
    outputs_dir = Path(args.outputs)

    try:
        bi_df, ci_df = _load_inputs(inputs_dir)
        result = run_evaluation(bi_df, ci_df, mode="local")
        payload = result.to_dict()
        payload["generated_at"] = datetime.now().isoformat()
        result_path = _save_result(outputs_dir, args.result_name, payload)
        print(f"[raspi_worker] 結果を書き出しました: {result_path}")
    except EvaluationError as exc:
        print(f"[raspi_worker] 評価に失敗しました: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
