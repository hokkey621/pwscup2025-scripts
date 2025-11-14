"""Raspberry Pi 評価ノード向けの設定ローダー。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
import json


CONFIG_FILENAME = "raspi-config.json"


@dataclass
class RemoteNodeConfig:
    host: str
    user: str
    repo_path: str
    port: int = 22
    identity_file: str | None = None
    ssh_common_args: list[str] = field(default_factory=list)
    uv_bin: str = "uv"
    remote_cache_dir: str = "webapp/outputs/.uv-cache"
    jobs_dir: str = "webapp/remote_jobs"
    result_filename: str = "result.json"

    def normalized_jobs_dir(self) -> Path:
        return Path(self.jobs_dir)


@dataclass
class DeploymentConfig:
    mode: Literal["local", "remote"] = "local"
    remote: RemoteNodeConfig | None = None

    @property
    def prefers_remote(self) -> bool:
        return self.mode == "remote" and self.remote is not None


def _as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def load_config(base_dir: Path | None = None) -> DeploymentConfig:
    """Load raspi-config.json if present; otherwise default to local mode."""

    base = base_dir or Path(__file__).resolve().parent
    config_path = base / CONFIG_FILENAME
    if not config_path.exists():
        return DeploymentConfig()

    with config_path.open(encoding="utf-8") as fp:
        payload = json.load(fp)

    mode = payload.get("mode", "local")
    remote_payload = payload.get("remote")

    if mode == "remote" and isinstance(remote_payload, dict):
        remote = RemoteNodeConfig(
            host=str(remote_payload.get("host")),
            user=str(remote_payload.get("user")),
            repo_path=str(remote_payload.get("repo_path")),
            port=int(remote_payload.get("port", 22)),
            identity_file=remote_payload.get("identity_file"),
            ssh_common_args=_as_list(remote_payload.get("ssh_common_args")),
            uv_bin=str(remote_payload.get("uv_bin", "uv")),
            remote_cache_dir=str(
                remote_payload.get("remote_cache_dir", "webapp/outputs/.uv-cache")
            ),
            jobs_dir=str(remote_payload.get("jobs_dir", "webapp/remote_jobs")),
            result_filename=str(remote_payload.get("result_filename", "result.json")),
        )
        return DeploymentConfig(mode="remote", remote=remote)

    return DeploymentConfig()
