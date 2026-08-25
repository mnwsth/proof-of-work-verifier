"""Domain models, independent of Google API payloads."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Status(StrEnum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"
    ERROR = "ERROR"
    INFO = "INFO"


class Decision(StrEnum):
    NONE = "none"
    IGNORE = "ignore"
    CONFIRMED = "confirmed"
    EXCEPTION = "exception"


class EventCode(StrEnum):
    INVALID_YOUTUBE_URL = "INVALID_YOUTUBE_URL"
    MISSING_VIDEO = "MISSING_VIDEO"
    MULTIPLE_VIDEOS = "MULTIPLE_VIDEOS"
    TEAM_MULTIPLE_VIDEOS = "TEAM_MULTIPLE_VIDEOS"
    UNMAPPED_STUDENT = "UNMAPPED_STUDENT"
    VIDEO_ID_CHANGED = "VIDEO_ID_CHANGED"
    VIDEO_UNAVAILABLE = "VIDEO_UNAVAILABLE"
    VIDEO_NOT_FOUND = "VIDEO_NOT_FOUND"
    CHANNEL_CHANGED = "CHANNEL_CHANGED"
    DURATION_CHANGED = "DURATION_CHANGED"
    PRIVACY_CHANGED = "PRIVACY_CHANGED"
    UPLOAD_STATUS_FAILURE = "UPLOAD_STATUS_FAILURE"
    VIDEO_UPLOADED_AFTER_SUBMISSION = "VIDEO_UPLOADED_AFTER_SUBMISSION"
    TITLE_CHANGED = "TITLE_CHANGED"
    DESCRIPTION_CHANGED = "DESCRIPTION_CHANGED"
    TAGS_CHANGED = "TAGS_CHANGED"
    CLASSROOM_SUBMISSION_RECLAIMED = "CLASSROOM_SUBMISSION_RECLAIMED"
    BASELINE_INCOMPLETE = "BASELINE_INCOMPLETE"
    API_ERROR = "API_ERROR"
    API_QUOTA_ERROR = "API_QUOTA_ERROR"
    NETWORK_ERROR = "NETWORK_ERROR"


EVENT_DESCRIPTIONS = {
    EventCode.INVALID_YOUTUBE_URL: "Submitted attachment is not a valid YouTube URL",
    EventCode.MISSING_VIDEO: "No YouTube video was submitted",
    EventCode.MULTIPLE_VIDEOS: "More than one YouTube video on a single submission",
    EventCode.TEAM_MULTIPLE_VIDEOS: "Teammates submitted different YouTube videos",
    EventCode.UNMAPPED_STUDENT: "Student is not mapped to a team in roster.csv",
    EventCode.VIDEO_ID_CHANGED: "Classroom attachment now points to a different YouTube video",
    EventCode.VIDEO_UNAVAILABLE: "Video unavailable",
    EventCode.VIDEO_NOT_FOUND: "Video unavailable",
    EventCode.CHANNEL_CHANGED: "Channel ID changed",
    EventCode.DURATION_CHANGED: "Duration changed",
    EventCode.PRIVACY_CHANGED: "Privacy status changed",
    EventCode.UPLOAD_STATUS_FAILURE: "YouTube upload or processing failed",
    EventCode.VIDEO_UPLOADED_AFTER_SUBMISSION: "YouTube publish time is after Classroom turn-in",
    EventCode.TITLE_CHANGED: "Title changed",
    EventCode.DESCRIPTION_CHANGED: "Description changed",
    EventCode.TAGS_CHANGED: "Tags changed",
    EventCode.CLASSROOM_SUBMISSION_RECLAIMED: "Classroom submission was unsubmitted or reclaimed",
    EventCode.BASELINE_INCOMPLETE: "Baseline duration is not frozen yet because the video was still processing",
    EventCode.API_ERROR: "YouTube or Classroom API error",
    EventCode.API_QUOTA_ERROR: "API quota exhausted",
    EventCode.NETWORK_ERROR: "Network error talking to Google APIs",
}


class RosterEntry(BaseModel):
    student_email: str = ""
    classroom_user_id: str = ""
    team_id: str = ""
    team_name: str = ""
    student_name: str = ""


class Submission(BaseModel):
    assignment_id: str
    team_id: str = ""
    team_name: str = ""
    students: str = ""
    classroom_user_id: str = ""
    classroom_submission_id: str = ""
    classroom_submission_state: str = ""
    classroom_late: bool | None = None
    submitted_at: str = ""
    youtube_url: str = ""
    video_id: str = ""
    first_seen_at: str = ""
    last_seen_at: str = ""
    current_status: str = ""
    classroom_alternate_link: str = ""
    event_codes: list[str] = Field(default_factory=list)
    reclaimed: bool = False


class VideoSnapshot(BaseModel):
    video_id: str | None = None
    channel_id: str | None = None
    channel_title: str | None = None
    published_at: str | None = None
    recording_date: str | None = None
    duration: str | None = None
    duration_seconds: int | None = None
    privacy_status: str | None = None
    upload_status: str | None = None
    license: str | None = None
    embeddable: bool | None = None
    made_for_kids: bool | None = None
    caption: str | None = None
    definition: str | None = None
    dimension: str | None = None
    has_custom_thumbnail: bool | None = None
    title: str | None = None
    description_hash: str | None = None
    tags_hash: str | None = None
    etag: str | None = None
    fingerprint: str | None = None
    unavailable: bool = False
    error_code: str | None = None
    raw: dict | None = None

    def is_processed(self) -> bool:
        return (self.upload_status or "") == "processed" and self.duration_seconds is not None

    def fingerprint_fields(self) -> dict:
        return {
            "video_id": self.video_id or "",
            "channel_id": self.channel_id or "",
            "published_at": self.published_at or "",
            "duration_seconds": self.duration_seconds,
            "privacy_status": self.privacy_status or "",
            "upload_status": self.upload_status or "",
            "title": self.title or "",
            "description_hash": self.description_hash or "",
            "tags_hash": self.tags_hash or "",
        }


class BaselineRow(BaseModel):
    assignment_id: str
    team_id: str
    classroom_submission_id: str = ""
    classroom_submitted_at: str = ""
    baseline_captured_at: str = ""
    youtube_url: str = ""
    video_id: str = ""
    channel_id: str = ""
    channel_title: str = ""
    published_at: str = ""
    recording_date: str = ""
    duration: str = ""
    duration_seconds: str = ""
    privacy_status: str = ""
    upload_status: str = ""
    license: str = ""
    embeddable: str = ""
    made_for_kids: str = ""
    caption: str = ""
    definition: str = ""
    dimension: str = ""
    has_custom_thumbnail: str = ""
    title: str = ""
    description_hash: str = ""
    tags_hash: str = ""
    etag: str = ""
    fingerprint: str = ""
    baseline_complete: str = "false"

    def snapshot(self) -> VideoSnapshot:
        seconds = int(self.duration_seconds) if self.duration_seconds not in ("", None) else None
        return VideoSnapshot(
            video_id=self.video_id or None,
            channel_id=self.channel_id or None,
            channel_title=self.channel_title or None,
            published_at=self.published_at or None,
            recording_date=self.recording_date or None,
            duration=self.duration or None,
            duration_seconds=seconds,
            privacy_status=self.privacy_status or None,
            upload_status=self.upload_status or None,
            license=self.license or None,
            embeddable=_optional_bool(self.embeddable),
            made_for_kids=_optional_bool(self.made_for_kids),
            caption=self.caption or None,
            definition=self.definition or None,
            dimension=self.dimension or None,
            has_custom_thumbnail=_optional_bool(self.has_custom_thumbnail),
            title=self.title or None,
            description_hash=self.description_hash or None,
            tags_hash=self.tags_hash or None,
            etag=self.etag or None,
            fingerprint=self.fingerprint or None,
        )

    def is_complete(self) -> bool:
        return self.baseline_complete == "true"


class Resolution(BaseModel):
    assignment_id: str
    team_id: str
    decision: str = Decision.NONE.value
    penalty_points: str = ""
    reason: str = ""
    decided_at: str = ""
    decided_by: str = ""
    related_check_timestamp: str = ""


class VerificationResult(BaseModel):
    assignment_id: str
    team_id: str
    team_name: str = ""
    classroom_submission_id: str = ""
    classroom_submission_time: str = ""
    baseline_captured_at: str = ""
    verification_time: str = ""
    youtube_url: str = ""
    baseline_video_id: str = ""
    current_video_id: str = ""
    video_exists: str = ""
    baseline_channel_id: str = ""
    current_channel_id: str = ""
    channel_match: str = ""
    baseline_published_at: str = ""
    current_published_at: str = ""
    baseline_duration: str = ""
    current_duration: str = ""
    duration_match: str = ""
    baseline_privacy_status: str = ""
    current_privacy_status: str = ""
    baseline_upload_status: str = ""
    current_upload_status: str = ""
    baseline_title: str = ""
    current_title: str = ""
    baseline_description_hash: str = ""
    current_description_hash: str = ""
    baseline_tags_hash: str = ""
    current_tags_hash: str = ""
    baseline_etag: str = ""
    current_etag: str = ""
    status: str = Status.ERROR.value
    event_codes: str = ""
    error_code: str = ""
    notes: str = ""
    events: list[str] = Field(default_factory=list)
    baseline: VideoSnapshot | None = None
    current: VideoSnapshot | None = None


class CheckMetadata(BaseModel):
    assignment_id: str
    status: str = "running"
    kind: str = "verification"
    started_at: str = ""
    completed_at: str = ""
    teams_expected: int = 0
    teams_checked: int = 0
    successful_checks: int = 0
    api_errors: int = 0
    green: int = 0
    yellow: int = 0
    red: int = 0
    error: int = 0


def _optional_bool(value: str | None) -> bool | None:
    if value in (None, ""):
        return None
    return value == "true"


RESULT_FIELDS = [
    "assignment_id",
    "team_id",
    "team_name",
    "classroom_submission_id",
    "classroom_submission_time",
    "baseline_captured_at",
    "verification_time",
    "youtube_url",
    "baseline_video_id",
    "current_video_id",
    "video_exists",
    "baseline_channel_id",
    "current_channel_id",
    "channel_match",
    "baseline_published_at",
    "current_published_at",
    "baseline_duration",
    "current_duration",
    "duration_match",
    "baseline_privacy_status",
    "current_privacy_status",
    "baseline_upload_status",
    "current_upload_status",
    "baseline_title",
    "current_title",
    "baseline_description_hash",
    "current_description_hash",
    "baseline_tags_hash",
    "current_tags_hash",
    "baseline_etag",
    "current_etag",
    "status",
    "event_codes",
    "error_code",
    "notes",
]

SUBMISSION_FIELDS = [
    "assignment_id",
    "team_id",
    "team_name",
    "students",
    "classroom_submission_id",
    "classroom_submission_state",
    "classroom_late",
    "submitted_at",
    "youtube_url",
    "video_id",
    "first_seen_at",
    "last_seen_at",
    "current_status",
]

BASELINE_FIELDS = [
    "assignment_id",
    "team_id",
    "classroom_submission_id",
    "classroom_submitted_at",
    "baseline_captured_at",
    "youtube_url",
    "video_id",
    "channel_id",
    "channel_title",
    "published_at",
    "recording_date",
    "duration",
    "duration_seconds",
    "privacy_status",
    "upload_status",
    "license",
    "embeddable",
    "made_for_kids",
    "caption",
    "definition",
    "dimension",
    "has_custom_thumbnail",
    "title",
    "description_hash",
    "tags_hash",
    "etag",
    "fingerprint",
    "baseline_complete",
]

ROSTER_FIELDS = [
    "student_email",
    "classroom_user_id",
    "team_id",
    "team_name",
    "student_name",
]

RESOLUTION_FIELDS = [
    "assignment_id",
    "team_id",
    "decision",
    "penalty_points",
    "reason",
    "decided_at",
    "decided_by",
    "related_check_timestamp",
]

EXPORT_FIELDS = [
    "team_id",
    "team_name",
    "submitted_at",
    "youtube_url",
    "video_id",
    "baseline_captured_at",
    "last_verified_at",
    "status",
    "events",
    "resolution",
    "penalty_points",
    "resolution_reason",
]
