"""PWS CUP 2025 評価パイプライン呼び出しラッパー。"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Literal

import pandas as pd

from . import DEFAULT_AI_PATH, DEFAULT_ANS_PATH, REPO_ROOT
from .raspi_config import DeploymentConfig, RemoteNodeConfig, load_config as load_raspi_config


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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "utility_score": self.utility_score,
            "privacy_score": self.privacy_score,
            "attack_success_total": self.attack_success_total,
            "validation_accuracy": self.validation_accuracy,
            "mia_message": self.mia_message,
            "logs": self.logs,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "EvaluationResult":
        return cls(
            utility_score=payload.get("utility_score"),
            privacy_score=payload.get("privacy_score"),
            attack_success_total=payload.get("attack_success_total"),
            validation_accuracy=payload.get("validation_accuracy"),
            mia_message=payload.get("mia_message", ""),
            logs=dict(payload.get("logs") or {}),
        )


UTILITY_RE = re.compile(r"Ci utility: ([0-9.]+) / 80")
VALIDATION_RE = re.compile(r"Validation Accuracy.*?: ([0-9.]+)")
ATTACK_TOTAL_RE = re.compile(r"TOTAL\s+(\d+)")


REMOTE_RESULT_PATH = METRICS_DIR / "remote_latest.json"
_DEPLOYMENT_CONFIG: DeploymentConfig | None = None


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


def _deployment_config() -> DeploymentConfig:
    global _DEPLOYMENT_CONFIG
    if _DEPLOYMENT_CONFIG is None:
        _DEPLOYMENT_CONFIG = load_raspi_config(Path(__file__).resolve().parent)
    return _DEPLOYMENT_CONFIG


def _persist_inputs(bi_prime: pd.DataFrame, ci: pd.DataFrame) -> tuple[Path, Path]:
    ensure_directories()
    bi_prime.to_csv(BI_OUTPUT_PATH, index=False)
    ci.to_csv(CI_OUTPUT_PATH, index=False)
    return BI_OUTPUT_PATH, CI_OUTPUT_PATH


def _build_metrics_payload(
    utility_score: float | None,
    privacy_score: float | None,
    attack_total: int | None,
    validation_accuracy: float | None,
) -> Dict[str, Any]:
    positives, total_records = _ans_stats()
    return {
        "timestamp": datetime.now().isoformat(),
        "utility_score": utility_score,
        "privacy_score": privacy_score,
        "attack_success_total": attack_total,
        "validation_accuracy": validation_accuracy,
        "ans_total_positive": positives,
        "ans_total_rows": total_records,
    }


def _write_metrics_file(payload: Dict[str, Any]) -> None:
    METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    METRICS_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _write_log_file(logs: Dict[str, str]) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_lines: list[str] = []
    for label, text in logs.items():
        log_lines.append(f"=== {label} ===")
        log_lines.append((text or "").strip())
        log_lines.append("")
    log_path = LOG_DIR / f"evaluation_{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"
    log_path.write_text("\n".join(log_lines), encoding="utf-8")


def _run_local_commands(bi_path: Path, ci_path: Path) -> EvaluationResult:
    logs: Dict[str, str] = {}
    fixed_bi_path = OUTPUT_DIR / "bi_prime_fixed.csv"

    fix_cmd = [
        "uv",
        "run",
        "python",
        "util/check_and_fix_csv.py",
        str(bi_path),
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
        str(ci_path),
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
        str(ci_path),
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
        str(ci_path),
        "-d",
    ]
    eval_res = _run_command(eval_cmd, "evaluation/eval_all.py")
    logs["evaluation/eval_all.py"] = eval_res.stdout + eval_res.stderr
    utility_score = _parse_float(UTILITY_RE, eval_res.stdout)

    positives, _ = _ans_stats()
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

    result = EvaluationResult(
        utility_score=utility_score,
        privacy_score=privacy_score,
        attack_success_total=attack_total,
        validation_accuracy=validation_accuracy,
        mia_message=mia_message,
        logs=logs,
    )

    metrics_payload = _build_metrics_payload(
        utility_score, privacy_score, attack_total, validation_accuracy
    )
    _write_metrics_file(metrics_payload)
    _write_log_file(logs)
    return result


def _apply_mode_preference(
    forced_mode: Literal["auto", "local", "remote"],
) -> Literal["local", "remote"]:
    config = _deployment_config()
    if forced_mode == "local":
        return "local"
    if forced_mode == "remote":
        if not config.prefers_remote:
            raise EvaluationError("remote モードが要求されましたが設定が見つかりません")
        return "remote"
    return "remote" if config.prefers_remote else "local"


def run_evaluation(
    bi_prime: pd.DataFrame,
    ci: pd.DataFrame,
    *,
    mode: Literal["auto", "local", "remote"] = "auto",
) -> EvaluationResult:
    """Bi'/Ciを一時保存し、公式スクリプト群を順次実行する。"""

    chosen = _apply_mode_preference(mode)
    if chosen == "remote":
        config = _deployment_config()
        return _run_remote_evaluation(bi_prime, ci, config.remote)
    return _run_local_evaluation(bi_prime, ci)


def _run_local_evaluation(bi_prime: pd.DataFrame, ci: pd.DataFrame) -> EvaluationResult:
    bi_path, ci_path = _persist_inputs(bi_prime, ci)
    return _run_local_commands(bi_path, ci_path)


def _run_remote_evaluation(
    bi_prime: pd.DataFrame,
    ci: pd.DataFrame,
    remote: RemoteNodeConfig | None,
) -> EvaluationResult:
    if remote is None:
        raise EvaluationError("remote ノードの設定が見つかりません")

    bi_path, ci_path = _persist_inputs(bi_prime, ci)
    result = _dispatch_remote_job(remote, bi_path, ci_path)
    metrics_payload = _build_metrics_payload(
        result.utility_score,
        result.privacy_score,
        result.attack_success_total,
        result.validation_accuracy,
    )
    _write_metrics_file(metrics_payload)
    _write_log_file(result.logs)
    return result


def _dispatch_remote_job(
    remote: RemoteNodeConfig,
    bi_path: Path,
    ci_path: Path,
) -> EvaluationResult:
    job_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    jobs_root = remote.normalized_jobs_dir()
    job_rel = jobs_root / job_id
    inputs_rel = job_rel / "inputs"
    outputs_rel = job_rel / "outputs"

    _run_ssh(
        remote,
        " && ".join(
            [
                f"mkdir -p {shlex.quote(_remote_absolute(remote, inputs_rel))}",
                f"mkdir -p {shlex.quote(_remote_absolute(remote, outputs_rel))}",
            ]
        ),
    )

    _copy_to_remote(remote, bi_path, inputs_rel / BI_OUTPUT_PATH.name)
    _copy_to_remote(remote, ci_path, inputs_rel / CI_OUTPUT_PATH.name)

    remote_cmd = (
        f"cd {shlex.quote(remote.repo_path)} && "
        f"UV_CACHE_DIR={shlex.quote(remote.remote_cache_dir)} "
        f"{shlex.quote(remote.uv_bin)} run python -m webapp.raspi_worker "
        f"--inputs {shlex.quote(str(inputs_rel))} "
        f"--outputs {shlex.quote(str(outputs_rel))} "
        f"--result-name {shlex.quote(remote.result_filename)}"
    )
    _run_ssh(remote, remote_cmd)

    local_result = REMOTE_RESULT_PATH
    local_result.parent.mkdir(parents=True, exist_ok=True)
    _fetch_from_remote(remote, outputs_rel / remote.result_filename, local_result)
    payload = json.loads(local_result.read_text(encoding="utf-8"))
    return EvaluationResult.from_dict(payload)


def _expand_identity(path_str: str | None) -> str | None:
    if not path_str:
        return None
    return os.path.expanduser(path_str)


def _ssh_base(remote: RemoteNodeConfig) -> list[str]:
    base = ["ssh", "-p", str(remote.port)]
    identity = _expand_identity(remote.identity_file)
    if identity:
        base += ["-i", identity]
    base += remote.ssh_common_args
    base.append(f"{remote.user}@{remote.host}")
    return base


def _scp_base(remote: RemoteNodeConfig) -> list[str]:
    base = ["scp", "-P", str(remote.port)]
    identity = _expand_identity(remote.identity_file)
    if identity:
        base += ["-i", identity]
    base += remote.ssh_common_args
    return base


def _run_ssh(remote: RemoteNodeConfig, command: str) -> None:
    cmd = _ssh_base(remote) + [command]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise EvaluationError(
            f"SSH コマンドが失敗しました: {' '.join(cmd)}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )


def _copy_to_remote(remote: RemoteNodeConfig, local_path: Path, remote_rel: Path) -> None:
    remote_abs = _remote_absolute(remote, remote_rel)
    dest = f"{remote.user}@{remote.host}:{remote_abs}"
    cmd = _scp_base(remote) + [str(local_path), dest]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise EvaluationError(
            f"ファイル送信に失敗しました: {' '.join(cmd)}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )


def _fetch_from_remote(remote: RemoteNodeConfig, remote_rel: Path, local_path: Path) -> None:
    remote_abs = _remote_absolute(remote, remote_rel)
    source = f"{remote.user}@{remote.host}:{remote_abs}"
    local_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = _scp_base(remote) + [source, str(local_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise EvaluationError(
            f"ファイル受信に失敗しました: {' '.join(cmd)}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )


def _remote_absolute(remote: RemoteNodeConfig, relative: Path) -> str:
    return str(Path(remote.repo_path) / relative)
