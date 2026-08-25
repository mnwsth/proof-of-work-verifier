"""Global and assignment configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = ROOT / "config.yaml"


class ApiConfig(BaseModel):
    youtube_batch_size: int = 50
    retry_attempts: int = 4
    retry_delays_seconds: list[float] = Field(default_factory=lambda: [0, 2, 5, 15])


class VerificationDefaults(BaseModel):
    default_duration_change_severity: str = "critical"
    default_title_change_severity: str = "warning"
    default_description_change_severity: str = "warning"
    duration_tolerance_seconds: int = 2
    baseline_delay_after_deadline: str = "PT15M"
    published_after_submission_grace_seconds: int = 300


class OAuthConfig(BaseModel):
    client_secrets_file: str = "./credentials/client_secrets.json"
    token_file: str = "./credentials/token.json"
    youtube_api_key_file: str = "./credentials/youtube_api_key.txt"


class AppConfig(BaseModel):
    timezone: str = "Asia/Kolkata"
    data_root: str = "./data/assignments"
    api: ApiConfig = Field(default_factory=ApiConfig)
    verification: VerificationDefaults = Field(default_factory=VerificationDefaults)
    oauth: OAuthConfig = Field(default_factory=OAuthConfig)

    @property
    def data_root_path(self) -> Path:
        path = Path(self.data_root)
        if not path.is_absolute():
            path = ROOT / path
        return path

    def resolve(self, relative: str) -> Path:
        path = Path(relative)
        if not path.is_absolute():
            path = ROOT / path
        return path


class MonitoringConfig(BaseModel):
    enabled: bool = True
    duration_tolerance_seconds: int = 2
    duration_change: str = "critical"
    channel_change: str = "critical"
    privacy_change_to_private: str = "critical"
    privacy_change_to_public: str = "warning"
    title_change: str = "warning"
    description_change: str = "warning"
    tags_change: str = "info"
    publication_time_anomaly: str = "warning"
    upload_status_failure: str = "critical"
    video_id_change: str = "critical"
    video_unavailable: str = "critical"


class AssignmentUiConfig(BaseModel):
    show_raw_values: bool = True


class AssignmentConfig(BaseModel):
    assignment_id: str
    name: str
    google_course_id: str = ""
    google_coursework_id: str = ""
    timezone: str = "Asia/Kolkata"
    deadline_at: str = ""
    baseline_delay_after_deadline: str = "PT15M"
    expected_artifact: str = "youtube"
    classroom_alternate_link: str = ""
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    ui: AssignmentUiConfig = Field(default_factory=AssignmentUiConfig)


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


def load_app_config(path: Path | None = None) -> AppConfig:
    config_path = path or DEFAULT_CONFIG_PATH
    return AppConfig.model_validate(load_yaml(config_path))


def dump_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False, allow_unicode=True)
