"""Shared test helpers."""

from __future__ import annotations

from app.config import AppConfig, AssignmentConfig
from app.models import Submission, VideoSnapshot
from app.storage import Storage
from app.utils import fingerprint_payload
from app.youtube import YouTubeSystemError, unavailable_snapshot
from app.verification import Verifier


def snapshot(**overrides) -> VideoSnapshot:
    data = dict(
        video_id="AAAAAAAAAAA",
        channel_id="UCchannelA",
        channel_title="Team Channel",
        published_at="2026-08-19T17:55:12+00:00",
        duration="PT4M18S",
        duration_seconds=258,
        privacy_status="unlisted",
        upload_status="processed",
        title="DS7 Team 17",
        description_hash="desc-hash-1",
        tags_hash="tags-hash-1",
        etag="etag-1",
    )
    data.update(overrides)
    snap = VideoSnapshot(**data)
    snap.fingerprint = fingerprint_payload(snap.fingerprint_fields())
    return snap


def assignment(assignment_id="DS07") -> AssignmentConfig:
    return AssignmentConfig(
        assignment_id=assignment_id,
        name="Digital Systems - Proof of Work 7",
        google_course_id="course1",
        google_coursework_id="work1",
        timezone="Asia/Kolkata",
        deadline_at="2026-08-20T23:59:00+05:30",
    )


def submission(**overrides) -> Submission:
    data = dict(
        assignment_id="DS07",
        team_id="T01",
        team_name="Team 01",
        students="A;B;C",
        classroom_submission_id="sub1",
        classroom_submission_state="TURNED_IN",
        classroom_late=False,
        submitted_at="2026-08-19T23:41:22+05:30",
        youtube_url="https://www.youtube.com/watch?v=AAAAAAAAAAA",
        video_id="AAAAAAAAAAA",
    )
    data.update(overrides)
    return Submission(**data)


class FakeYouTube:
    def __init__(self, mapping: dict | None = None, error: YouTubeSystemError | None = None):
        self.mapping = mapping or {}
        self.error = error
        self.calls: list[list[str]] = []

    def fetch(self, video_ids: list[str]) -> dict[str, VideoSnapshot]:
        self.calls.append(list(video_ids))
        if self.error:
            raise self.error
        results = {}
        for video_id in video_ids:
            results[video_id] = self.mapping.get(video_id, unavailable_snapshot(video_id))
        return results


class FakeClassroom:
    def __init__(self, submissions=None, students=None):
        self.submissions = submissions or []
        self.students = students or []

    def list_student_submissions(self, course_id, coursework_id):
        return self.submissions

    def list_students(self, course_id):
        return self.students


def make_storage(tmp_path) -> Storage:
    storage = Storage(tmp_path)
    storage.create_assignment(assignment())
    return storage


def make_verifier(tmp_path, youtube=None, classroom=None) -> Verifier:
    config = AppConfig(data_root=str(tmp_path), timezone="Asia/Kolkata")
    storage = Storage(tmp_path)
    storage.create_assignment(assignment())
    return Verifier(config, storage, youtube or FakeYouTube(), classroom)
