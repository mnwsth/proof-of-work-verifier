"""Severity mapping and human-readable event copy."""

from __future__ import annotations

from app.config import MonitoringConfig
from app.models import EVENT_DESCRIPTIONS, EventCode, Status

SEVERITY_STATUS = {
    "critical": Status.RED,
    "warning": Status.YELLOW,
    "info": Status.INFO,
    "error": Status.ERROR,
}

STATUS_RANK = {
    Status.GREEN: 0,
    Status.INFO: 0,
    Status.YELLOW: 1,
    Status.RED: 2,
    Status.ERROR: 3,
}


def severity_for(event: str, monitoring: MonitoringConfig) -> str:
    mapping = {
        EventCode.DURATION_CHANGED.value: monitoring.duration_change,
        EventCode.CHANNEL_CHANGED.value: monitoring.channel_change,
        EventCode.TITLE_CHANGED.value: monitoring.title_change,
        EventCode.DESCRIPTION_CHANGED.value: monitoring.description_change,
        EventCode.TAGS_CHANGED.value: monitoring.tags_change,
        EventCode.VIDEO_UPLOADED_AFTER_SUBMISSION.value: monitoring.publication_time_anomaly,
        EventCode.UPLOAD_STATUS_FAILURE.value: monitoring.upload_status_failure,
        EventCode.VIDEO_ID_CHANGED.value: monitoring.video_id_change,
        EventCode.VIDEO_UNAVAILABLE.value: monitoring.video_unavailable,
        EventCode.VIDEO_NOT_FOUND.value: monitoring.video_unavailable,
        EventCode.MISSING_VIDEO.value: "critical",
        EventCode.INVALID_YOUTUBE_URL.value: "critical",
        EventCode.MULTIPLE_VIDEOS.value: "critical",
        EventCode.TEAM_MULTIPLE_VIDEOS.value: "critical",
        EventCode.UNMAPPED_STUDENT.value: "critical",
        EventCode.CLASSROOM_SUBMISSION_RECLAIMED.value: "warning",
        EventCode.BASELINE_INCOMPLETE.value: "info",
        EventCode.API_ERROR.value: "error",
        EventCode.API_QUOTA_ERROR.value: "error",
        EventCode.NETWORK_ERROR.value: "error",
    }
    return mapping.get(event, "warning")


def status_for_events(
    events: list[str],
    monitoring: MonitoringConfig,
    overrides: dict[str, str] | None = None,
) -> Status:
    rank = 0
    result = Status.GREEN
    overrides = overrides or {}
    for event in events:
        severity = overrides.get(event) or severity_for(event, monitoring)
        status = SEVERITY_STATUS.get(severity, Status.YELLOW)
        if STATUS_RANK[status] > rank:
            rank = STATUS_RANK[status]
            result = status
    if result == Status.INFO:
        return Status.GREEN
    return result


def describe(event: str) -> str:
    try:
        return EVENT_DESCRIPTIONS[EventCode(event)]
    except ValueError:
        return event.replace("_", " ").title()


def describe_many(events: list[str] | str) -> str:
    if isinstance(events, str):
        items = [part for part in events.split(";") if part]
    else:
        items = events
    return "; ".join(describe(item) for item in items)


def privacy_event_severity(current: str | None, monitoring: MonitoringConfig) -> str:
    if current == "private":
        return monitoring.privacy_change_to_private
    if current == "public":
        return monitoring.privacy_change_to_public
    if not current:
        return monitoring.privacy_change_to_private
    return "warning"
