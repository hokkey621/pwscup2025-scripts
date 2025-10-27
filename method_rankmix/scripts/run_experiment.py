from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

from anonymize import load_config, run_anonymization, seed_everything


def parse_metrics(text: str) -> dict:
    patterns = {
        "stats_diff_max_abs": r"stats_diff max_abs: ([0-9.]+)",
        "lr_asthma_max_abs": r"LR_asthma_diff max_abs: ([0-9.]+)",
        "kw_ind_max_abs": r"KW_IND_diff max_abs: ([0-9.]+)",
        "ci_utility": r"Ci utility: ([0-9.]+) / 80",
    }
    results = {}
    for key, pat in patterns.items():
        match = re.search(pat, text)
        if match:
            results[key] = float(match.group(1))
    return results


def build_eval_cmd(args: argparse.Namespace) -> list[str]:
    cmd = [
        "uv",
        "run",
        "python",
        "evaluation/eval_all.py",
        args.bi,
        args.ci,
    ]
    if args.force:
        cmd.append("-f")
    if args.print_details:
        cmd.append("-d")
    return cmd


def main() -> None:
    parser = argparse.ArgumentParser(description="Ci 生成と採点をまとめて実行")
    parser.add_argument("--bi", required=True, help="入力 Bi.csv")
    parser.add_argument("--ci", required=True, help="出力 Ci.csv")
    parser.add_argument(
        "--config",
        default="config/params.json",
        help="匿名化パラメータ(JSON)",
    )
    parser.add_argument("--seed", type=int, default=None, help="乱数シード")
    default_log_dir = Path(__file__).resolve().parents[1] / "outputs" / "logs"
    parser.add_argument(
        "--log-dir",
        default=str(default_log_dir),
        help="評価ログを保存するディレクトリ",
    )
    parser.add_argument(
        "--metrics-json",
        default=None,
        help="スコアをJSONで保存するパス",
    )
    parser.add_argument(
        "--print-details",
        action="store_true",
        help="evaluation/eval_all.py -d を付与",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ci フォーマット異常時も -f で採点",
    )
    args = parser.parse_args()

    bi_path = Path(args.bi)
    ci_path = Path(args.ci)
    log_dir = Path(args.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    ci_path.parent.mkdir(parents=True, exist_ok=True)

    params = load_config(Path(args.config))
    seed_everything(args.seed)
    run_anonymization(bi_path, ci_path, params)

    eval_cmd = build_eval_cmd(args)
    completed = subprocess.run(
        eval_cmd,
        check=True,
        capture_output=True,
        text=True,
    )

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = log_dir / f"{ci_path.stem}_{timestamp}.log"
    log_text = completed.stdout + "\n" + completed.stderr
    log_path.write_text(log_text, encoding="utf-8")

    metrics = parse_metrics(completed.stdout)
    if args.metrics_json:
        Path(args.metrics_json).parent.mkdir(parents=True, exist_ok=True)
        with open(args.metrics_json, "w", encoding="utf-8") as fp:
            json.dump(metrics, fp, indent=2)

    print("=== Evaluation Output ===")
    print(completed.stdout)
    if metrics:
        print("=== Parsed Metrics ===")
        print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
