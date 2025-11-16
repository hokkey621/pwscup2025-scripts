from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

from ano import run_anonymization


def parse_metrics(text: str) -> dict[str, float]:
    number = r"([0-9.eE+\-]+)"
    patterns = {
        "stats_diff_max_abs": rf"stats_diff max_abs: {number}",
        "lr_asthma_max_abs": rf"LR_asthma_diff max_abs: {number}",
        "kw_ind_max_abs": rf"KW_IND_diff max_abs: {number}",
        "ci_utility": rf"Ci utility: {number} / 80",
    }
    results: dict[str, float] = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            results[key] = float(match.group(1))
    return results


def format_metrics_summary(metrics: dict[str, float]) -> list[str]:
    mapping: list[tuple[str, str, bool]] = [
        ("stats_diff_max_abs", "統計差分 (max abs)", True),
        ("lr_asthma_max_abs", "LR(asthma) 差分", True),
        ("kw_ind_max_abs", "KW独立性差分", True),
        ("ci_utility", "Ci utility (/80)", False),
    ]
    lines: list[str] = []
    for key, label, show_complement in mapping:
        val = metrics.get(key)
        if val is None:
            continue
        if show_complement:
            complement = max(0.0, min(1.0, 1.0 - val))
            lines.append(f"{label:<24}: {val:>7.4f}  (1 - diff = {complement:>7.4f})")
        else:
            lines.append(f"{label:<24}: {val:>7.4f}")
    return lines


def parse_validation_accuracy(text: str) -> float | None:
    match = re.search(r"Validation Accuracy.*?: ([0-9.]+)", text)
    if match:
        return float(match.group(1))
    return None


def parse_attack_total(text: str) -> int | None:
    match = re.search(r"TOTAL\s+(\d+)", text)
    if match:
        return int(match.group(1))
    return None


def run_subprocess(cmd: list[str], *, label: str) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )
    print(f"=== {label} ===")
    if completed.stdout:
        print(completed.stdout, end="" if completed.stdout.endswith("\n") else "\n")
    if completed.stderr:
        print(completed.stderr, end="" if completed.stderr.endswith("\n") else "\n")
    if completed.returncode != 0:
        print(f"[WARN] {label} は終了コード {completed.returncode} で停止しました。")
    return completed


def locate_repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "util").is_dir():
            return parent
    return here.parents[-1]


def resolve_python_exec(repo_root: Path) -> str:
    venv_python = repo_root / ".venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return "python3"


def main() -> None:
    repo_root = locate_repo_root()
    python_exec = resolve_python_exec(repo_root)
    template_root = Path(__file__).resolve().parents[1]
    default_bi = repo_root / "data" / "HI_10K.csv"
    default_ci = template_root / "outputs" / "ci" / "ci_output.csv"
    default_range = repo_root / "data" / "columns_range.json"
    default_log_dir = template_root / "outputs" / "logs"

    parser = argparse.ArgumentParser(
        description="template/scripts/ano.py を呼び出し、Ci生成から評価まで一括で実行するスクリプト"
    )
    parser.add_argument("--bi", default=str(default_bi), help="入力 Bi.csv（既定: data/HI_10K.csv）")
    parser.add_argument(
        "--ci",
        default=str(default_ci),
        help="出力 Ci.csv（既定: template/outputs/ci/ci_output.csv）",
    )
    parser.add_argument(
        "--ai",
        default=str(repo_root / "data" / "HI_100K.csv"),
        help="Ai.csv（攻撃評価用、既定: data/HI_100K.csv）",
    )
    parser.add_argument(
        "--ans",
        default=str(repo_root / "data" / "HI_ans.csv"),
        help="攻撃結果評価用の正解CSV（既定: data/HI_ans.csv）",
    )
    parser.add_argument(
        "--model-json",
        default=None,
        help="Di モデルの出力先（既定: outputs/model/<Ci名>.json）",
    )
    parser.add_argument(
        "--attack-output",
        default=None,
        help="攻撃結果CSVの出力先（既定: outputs/attack/<Ci名>_attack.csv）",
    )
    parser.add_argument(
        "--train-target",
        default="stroke_flag",
        help="Di 学習時のターゲット列名（既定: stroke_flag）",
    )
    parser.add_argument(
        "--skip-privacy",
        action="store_true",
        help="匿名性評価（Di 学習・攻撃・評価）をスキップする",
    )
    parser.add_argument("--seed", type=int, default=None, help="ano.py に渡す乱数シード（任意）")
    parser.add_argument(
        "--tail-ratio",
        type=float,
        default=0.05,
        help="t分布で外れ値とみなす割合（例: 0.05 で5%%）",
    )
    parser.add_argument(
        "--max-clusters",
        type=int,
        default=3,
        help="外れ値領域に適用するk-meansの最大クラスタ数",
    )
    parser.add_argument(
        "--range-json",
        default=str(default_range),
        help="util/check_csv.py 用 columns_range.json（既定: data/columns_range.json）",
    )
    parser.add_argument(
        "--skip-check",
        action="store_true",
        help="Ci 生成後の util/check_csv.py をスキップする",
    )
    parser.add_argument(
        "--no-fix-bi",
        dest="fix_bi",
        action="store_false",
        help="Bi を util/check_and_fix_csv.py で補正せず、そのまま利用する",
    )
    parser.set_defaults(fix_bi=True)
    parser.add_argument(
        "--log-dir",
        default=str(default_log_dir),
        help="ログ保存先（既定: template/outputs/logs）",
    )
    parser.add_argument(
        "--metrics-json",
        default=None,
        help="評価指標を JSON で書き出すパス（任意）",
    )
    parser.add_argument(
        "--print-details",
        action="store_true",
        help="evaluation/eval_all.py に -d を付与して詳細出力を得る",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ci のフォーマット異常があっても -f で採点を続行する",
    )
    args = parser.parse_args()

    bi_path = Path(args.bi)
    ci_path = Path(args.ci)
    ai_path = Path(args.ai)
    ans_path = Path(args.ans)
    log_dir = Path(args.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    ci_path.parent.mkdir(parents=True, exist_ok=True)

    log_sections: list[str] = []

    bi_for_use = bi_path
    if args.fix_bi:
        fix_dir = log_dir / "bi_fixed"
        fix_dir.mkdir(parents=True, exist_ok=True)
        fixed_bi_path = fix_dir / f"{bi_path.stem}_fixed.csv"
        fix_cmd = [
            python_exec,
            str(repo_root / "util" / "check_and_fix_csv.py"),
            str(bi_path),
            args.range_json,
            str(fixed_bi_path),
        ]
        fix_res = run_subprocess(fix_cmd, label="util/check_and_fix_csv.py (Bi)")
        block = ["# util/check_and_fix_csv.py (Bi) stdout", fix_res.stdout]
        if fix_res.stderr:
            block.extend(["# util/check_and_fix_csv.py (Bi) stderr", fix_res.stderr])
        if fix_res.returncode != 0:
            log_sections.append("\n".join(block))
            raise SystemExit("[ERROR] Bi の補正に失敗しました。ログを確認してください。")
        log_sections.append("\n".join(block))
        bi_for_use = fixed_bi_path

    run_anonymization(
        bi_for_use,
        ci_path,
        seed=args.seed,
        tail_ratio=args.tail_ratio,
        max_clusters=args.max_clusters,
    )

    privacy_summary_lines: list[str] = []

    check_failed = False
    if not args.skip_check:
        check_cmd = [
            python_exec,
            str(repo_root / "util" / "check_csv.py"),
            str(ci_path),
            args.range_json,
        ]
        check_res = run_subprocess(check_cmd, label="util/check_csv.py")
        block = ["# util/check_csv.py stdout", check_res.stdout]
        if check_res.stderr:
            block.extend(["# util/check_csv.py stderr", check_res.stderr])
        log_sections.append("\n".join(block))
        if check_res.returncode != 0:
            check_failed = True

    if not args.skip_privacy:
        model_path = Path(args.model_json) if args.model_json else (template_root / "outputs" / "model" / f"{ci_path.stem}.json")
        attack_output = Path(args.attack_output) if args.attack_output else (template_root / "outputs" / "attack" / f"{ci_path.stem}_attack.csv")
        model_path.parent.mkdir(parents=True, exist_ok=True)
        attack_output.parent.mkdir(parents=True, exist_ok=True)

        train_cmd = [
            python_exec,
            str(repo_root / "analysis" / "xgbt_train.py"),
            str(ci_path),
            "--model-json",
            str(model_path),
            "--target",
            args.train_target,
        ]
        if args.seed is not None:
            train_cmd.extend(["--seed", str(args.seed)])
        train_res = run_subprocess(train_cmd, label="analysis/xgbt_train.py")
        train_block = ["# analysis/xgbt_train.py stdout", train_res.stdout]
        if train_res.stderr:
            train_block.extend(["# analysis/xgbt_train.py stderr", train_res.stderr])
        log_sections.append("\n".join(train_block))
        if train_res.returncode != 0:
            raise SystemExit("[ERROR] Di 学習に失敗しました。ログを確認してください。")
        val_acc = parse_validation_accuracy(train_res.stdout)
        if val_acc is not None:
            privacy_summary_lines.append(f"Validation Accuracy (Di) : {val_acc:0.4f}")

        attack_cmd = [
            python_exec,
            str(repo_root / "attack" / "attack_example.py"),
            str(ai_path),
            str(ci_path),
            str(model_path),
            "-o",
            str(attack_output),
        ]
        attack_res = run_subprocess(attack_cmd, label="attack/attack_example.py")
        attack_block = ["# attack/attack_example.py stdout", attack_res.stdout]
        if attack_res.stderr:
            attack_block.extend(["# attack/attack_example.py stderr", attack_res.stderr])
        log_sections.append("\n".join(attack_block))
        if attack_res.returncode != 0:
            raise SystemExit("[ERROR] 攻撃スクリプトが失敗しました。ログを確認してください。")
        privacy_summary_lines.append(f"Attack result CSV      : {attack_output}")

        if ans_path.exists():
            check_ans_cmd = [
                python_exec,
                str(repo_root / "evaluation" / "check_ans.py"),
                str(attack_output),
                str(ans_path),
            ]
            check_ans_res = run_subprocess(check_ans_cmd, label="evaluation/check_ans.py")
            check_ans_block = ["# evaluation/check_ans.py stdout", check_ans_res.stdout]
            if check_ans_res.stderr:
                check_ans_block.extend(["# evaluation/check_ans.py stderr", check_ans_res.stderr])
            log_sections.append("\n".join(check_ans_block))
            if check_ans_res.returncode != 0:
                raise SystemExit("[ERROR] 攻撃結果の評価に失敗しました。ログを確認してください。")
            total = parse_attack_total(check_ans_res.stdout)
            if total is not None:
                privacy_summary_lines.append(f"Attack success (TOTAL) : {total}")
        else:
            privacy_summary_lines.append(f"[WARN] 正解CSVが存在しないため check_ans.py をスキップしました: {ans_path}")

    eval_cmd = [
        python_exec,
        str(repo_root / "evaluation" / "eval_all.py"),
        str(bi_for_use),
        str(ci_path),
    ]
    if args.force:
        eval_cmd.append("-f")
    if args.print_details:
        eval_cmd.append("-d")
    eval_res = run_subprocess(eval_cmd, label="evaluation/eval_all.py")
    block = ["# evaluation/eval_all.py stdout", eval_res.stdout]
    if eval_res.stderr:
        block.extend(["# evaluation/eval_all.py stderr", eval_res.stderr])
    log_sections.append("\n".join(block))

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = log_dir / f"{ci_path.stem}_{timestamp}.log"
    if eval_res.returncode == 0:
        metrics = parse_metrics(eval_res.stdout)
        if args.metrics_json:
            metrics_path = Path(args.metrics_json)
            metrics_path.parent.mkdir(parents=True, exist_ok=True)
            with metrics_path.open("w", encoding="utf-8") as fp:
                json.dump(metrics, fp, indent=2, ensure_ascii=False)

        summary_lines = format_metrics_summary(metrics)
        if summary_lines:
            print("=== Metrics Summary ===")
            for line in summary_lines:
                print(line)
            log_sections.append("# Metrics Summary\n" + "\n".join(summary_lines))

        if metrics:
            print("=== Parsed Metrics (JSON) ===")
            print(json.dumps(metrics, indent=2, ensure_ascii=False))

    if privacy_summary_lines:
        print("=== Privacy Summary ===")
        for line in privacy_summary_lines:
            print(line)
        log_sections.append("# Privacy Summary\n" + "\n".join(privacy_summary_lines))

    log_path.write_text("\n\n".join(log_sections), encoding="utf-8")
    print(f"[INFO] ログを保存しました: {log_path}")
    if args.metrics_json and eval_res.returncode == 0:
        print(f"[INFO] メトリクスを保存しました: {args.metrics_json}")

    if check_failed:
        raise SystemExit("[ERROR] util/check_csv.py でエラーが発生しました。ログを確認してください。")
    if eval_res.returncode != 0:
        raise SystemExit("[ERROR] evaluation/eval_all.py が失敗しました。ログを確認してください。")



if __name__ == "__main__":
    main()
