"""ラズベリーパイ向けデモ用のワンショット実行スクリプト。

フォーム初期値（および任意の上書き）をBiへ追加→匿名化→評価まで
1コマンドで実行し、サマリを標準出力に表示する。
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from webapp import DEFAULT_BI_PATH
from webapp import anonymize, evaluate


def _load_entry_overrides(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    with path.open("r", encoding="utf-8") as fp:
        data = json.load(fp)
        if not isinstance(data, dict):
            raise ValueError("entry JSON はオブジェクト形式で指定してください。")
        return data


def _merge_entry(
    defaults: dict[str, Any], overrides: dict[str, Any]
) -> dict[str, Any]:
    merged = defaults.copy()
    merged.update(overrides)
    return merged


def run_demo_once(
    *,
    algorithm: str,
    entry_overrides_path: Path | None = None,
    bi_path: Path = Path(DEFAULT_BI_PATH),
    output_json: Path | None = None,
) -> dict[str, Any]:
    base_bi = anonymize.load_base_bi(bi_path)
    profiles = anonymize.build_column_profiles(base_bi)
    defaults = anonymize.default_form_values(profiles)
    overrides = _load_entry_overrides(entry_overrides_path)
    entry = _merge_entry(defaults, overrides)

    result = anonymize.run_anonymization(
        base_bi,
        profiles,
        entry,
        algorithm,
    )

    eval_result = evaluate.run_evaluation(result.bi_prime, result.ci)
    payload: dict[str, Any] = {
        "algorithm": algorithm,
        "entry": result.entry,
        "new_row_index": result.new_index,
        "evaluation": asdict(eval_result),
    }

    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return payload


def _print_summary(payload: dict[str, Any]) -> None:
    evaluation = payload["evaluation"]
    print("=== Raspberry Pi Demo Run ===")
    print(f"Algorithm : {payload['algorithm']}")
    print(f"New Row   : {payload['new_row_index']}")
    print("---- Evaluation ----")
    print(f"Utility Score : {evaluation.get('utility_score')}")
    print(f"Privacy Score : {evaluation.get('privacy_score')}")
    print(f"Di Accuracy   : {evaluation.get('validation_accuracy')}")
    print(f"MIA Message   : {evaluation.get('mia_message')}")
    print("---------------------")
    print("詳細ログは webapp/outputs/logs/ を参照してください。")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Raspberry Pi デモ用: 匿名化〜評価を一括実行します。"
    )
    parser.add_argument(
        "--algorithm",
        default="main",
        help="使用するアルゴリズムID (default: main)",
    )
    parser.add_argument(
        "--entry-json",
        type=Path,
        help="フォーム上書き値を記した JSON ファイルへのパス",
    )
    parser.add_argument(
        "--bi-path",
        type=Path,
        default=Path(DEFAULT_BI_PATH),
        help="ベースとなる Bi CSV のパス",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        help="実行結果サマリを書き出す JSON ファイルパス",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = run_demo_once(
        algorithm=args.algorithm,
        entry_overrides_path=args.entry_json,
        bi_path=args.bi_path,
        output_json=args.output_json,
    )
    _print_summary(payload)


if __name__ == "__main__":
    main()
