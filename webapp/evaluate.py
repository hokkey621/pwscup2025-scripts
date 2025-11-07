"""PWS CUP 2025 評価パイプライン呼び出しラッパー。"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

import pandas as pd

from . import DEFAULT_AI_PATH, DEFAULT_ANS_PATH, REPO_ROOT


OUTPUT_DIR = Path(__file__).resolve().parent / "outputs"
BI_OUTPUT_PATH = OUTPUT_DIR / "bi_prime.csv"
CI_OUTPUT_PATH = OUTPUT_DIR / "ci_result.csv"
MODEL_DIR = OUTPUT_DIR / "model"
ATTACK_DIR = OUTPUT_DIR / "attack"
METRICS_DIR = OUTPUT_DIR / "metrics"
LOG_DIR = OUTPUT_DIR / "logs"
MODEL_PATH = MODEL_DIR / "di_model.json"
ATTACK_PATH = ATTACK_DIR / "attack_result.csv"
METRICS_PATH = METRICS_DIR / "latest.json"
UV_CACHE_DIR = OUTPUT_DIR / ".uv-cache"
RANGE_JSON_PATH = REPO_ROOT / "data" / "columns_range.json"


class EvaluationError(Exception):
    """評価フロー失敗時の例外。"""


@dataclass
class EvaluationResult:
    """Streamlit表示用の評価結果。"""

    utility_score: float | None
    privacy_score: float | None
    attack_success_total: int | None
    validation_accuracy: float | None
    mia_message: str
    logs: Dict[str, str]


UTILITY_RE = re.compile(r"Ci utility: ([0-9.]+) / 80")
VALIDATION_RE = re.compile(r"Validation Accuracy.*?: ([0-9.]+)")
ATTACK_TOTAL_RE = re.compile(r"TOTAL\s+(\d+)")


def ensure_directories() -> None:
    """評価で利用する出力ディレクトリを作成する。"""

    for path in [OUTPUT_DIR, MODEL_DIR, ATTACK_DIR, METRICS_DIR, LOG_DIR, UV_CACHE_DIR]:
        path.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def _ans_stats(ans_path: Path = DEFAULT_ANS_PATH) -> tuple[int, int]:
    ans_series = pd.read_csv(ans_path, header=None).iloc[:, 0]
    positives = int((pd.to_numeric(ans_series, errors="coerce") == 1).sum())
    total = int(len(ans_series))
    return positives, total


def _run_command(cmd: list[str], label: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.setdefault("UV_CACHE_DIR", str(UV_CACHE_DIR))

    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        raise EvaluationError(
            f"{label} が失敗しました。\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result


def _parse_float(pattern: re.Pattern[str], text: str) -> float | None:
    match = pattern.search(text)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None


def _parse_int(pattern: re.Pattern[str], text: str) -> int | None:
    match = pattern.search(text)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


def run_evaluation(bi_prime: pd.DataFrame, ci: pd.DataFrame) -> EvaluationResult:
    """Bi'/Ciを一時保存し、公式スクリプト群を順次実行する。"""

    ensure_directories()
    bi_prime.to_csv(BI_OUTPUT_PATH, index=False)
    ci.to_csv(CI_OUTPUT_PATH, index=False)

    logs: Dict[str, str] = {}

    fixed_bi_path = OUTPUT_DIR / "bi_prime_fixed.csv"

    fix_cmd = [
        "uv",
        "run",
        "python",
        "util/check_and_fix_csv.py",
        str(BI_OUTPUT_PATH),
        str(RANGE_JSON_PATH),
        str(fixed_bi_path),
    ]
    fix_res = _run_command(fix_cmd, "util/check_and_fix_csv.py")
    logs["util/check_and_fix_csv.py"] = fix_res.stdout + fix_res.stderr

    train_cmd = [
        "uv",
        "run",
        "python",
        "analysis/xgbt_train.py",
        str(CI_OUTPUT_PATH),
        "--model-json",
        str(MODEL_PATH),
        "--target",
        "stroke_flag",
    ]
    train_res = _run_command(train_cmd, "analysis/xgbt_train.py")
    logs["analysis/xgbt_train.py"] = train_res.stdout + train_res.stderr
    validation_accuracy = _parse_float(VALIDATION_RE, train_res.stdout)

    attack_cmd = [
        "uv",
        "run",
        "python",
        "attack/attack_example.py",
        str(DEFAULT_AI_PATH),
        str(CI_OUTPUT_PATH),
        str(MODEL_PATH),
        "-o",
        str(ATTACK_PATH),
    ]
    attack_res = _run_command(attack_cmd, "attack/attack_example.py")
    logs["attack/attack_example.py"] = attack_res.stdout + attack_res.stderr

    check_cmd = [
        "uv",
        "run",
        "python",
        "evaluation/check_ans.py",
        str(ATTACK_PATH),
        str(DEFAULT_ANS_PATH),
    ]
    check_res = _run_command(check_cmd, "evaluation/check_ans.py")
    logs["evaluation/check_ans.py"] = check_res.stdout + check_res.stderr
    attack_total = _parse_int(ATTACK_TOTAL_RE, check_res.stdout)

    eval_cmd = [
        "uv",
        "run",
        "python",
        "evaluation/eval_all.py",
        str(fixed_bi_path),
        str(CI_OUTPUT_PATH),
        "-d",
    ]
    eval_res = _run_command(eval_cmd, "evaluation/eval_all.py")
    logs["evaluation/eval_all.py"] = eval_res.stdout + eval_res.stderr
    utility_score = _parse_float(UTILITY_RE, eval_res.stdout)

    positives, total_records = _ans_stats()
    if attack_total is not None and positives > 0:
        privacy_score = max(0.0, min(1.0, 1.0 - attack_total / positives))
    else:
        privacy_score = None

    if attack_total is None:
        mia_message = "MIA結果を取得できませんでした。"
    else:
        mia_message = (
            f"攻撃成功件数: {attack_total} / {positives}"
            if positives
            else f"攻撃成功件数: {attack_total}"
        )

    metrics_payload: Dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "utility_score": utility_score,
        "privacy_score": privacy_score,
        "attack_success_total": attack_total,
        "validation_accuracy": validation_accuracy,
        "ans_total_positive": positives,
        "ans_total_rows": total_records,
    }
    METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    METRICS_PATH.write_text(json.dumps(metrics_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    log_lines = []
    for label, text in logs.items():
        log_lines.append(f"=== {label} ===")
        log_lines.append(text.strip())
        log_lines.append("")
    log_path = LOG_DIR / f"evaluation_{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"
    log_path.write_text("\n".join(log_lines), encoding="utf-8")

    return EvaluationResult(
        utility_score=utility_score,
        privacy_score=privacy_score,
        attack_success_total=attack_total,
        validation_accuracy=validation_accuracy,
        mia_message=mia_message,
        logs=logs,
    )
