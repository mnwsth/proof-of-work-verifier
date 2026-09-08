"""Global and assignment configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = ROOT / "config.yaml"
LOCAL_CONFIG_PATH = ROOT / "config.local.yaml"


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
    allowed_spreadsheet_ids: list[str] = Field(default_factory=list)


class GoogleConfig(BaseModel):
    classroom_course_id: str = ""
    admin_folder_id: str = ""
    reflections_folder_id: str = ""
    reflections_topic_id: str = ""

    @field_validator(
        "classroom_course_id",
        "admin_folder_id",
        "reflections_folder_id",
        "reflections_topic_id",
        mode="before",
    )
    @classmethod
    def ids_as_str(cls, value: object) -> str:
        if value is None:
            return ""
        return str(value)


class AppConfig(BaseModel):
    timezone: str = "Asia/Kolkata"
    data_root: str = "./data/assignments"
    api: ApiConfig = Field(default_factory=ApiConfig)
    verification: VerificationDefaults = Field(default_factory=VerificationDefaults)
    oauth: OAuthConfig = Field(default_factory=OAuthConfig)
    google: GoogleConfig = Field(default_factory=GoogleConfig)

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


def merge_dicts(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_app_config(path: Path | None = None) -> AppConfig:
    config_path = path or DEFAULT_CONFIG_PATH
    data = load_yaml(config_path)
    if path is None:
        data = merge_dicts(data, load_yaml(LOCAL_CONFIG_PATH))
    return AppConfig.model_validate(data)


def require_course_id(config: AppConfig) -> str:
    course_id = (config.google.classroom_course_id or "").strip()
    if not course_id:
        raise SystemExit("Set google.classroom_course_id in config.local.yaml")
    return course_id


def dump_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False, allow_unicode=True)
