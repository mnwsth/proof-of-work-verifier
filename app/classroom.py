"""Google Classroom adapter. Instructor-read only."""

from __future__ import annotations

import logging
from typing import Any

from datetime import datetime, timezone

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.models import RosterEntry
from app.utils import extract_video_id, format_iso, parse_iso, zone
from app.youtube import parse_and_canonicalize

LOGGER = logging.getLogger("verifier")

TURNED_IN = "TURNED_IN"
RECLAIMED = "RECLAIMED_BY_STUDENT"


class ClassroomClient:
    def __init__(self, credentials, service=None):
        self.credentials = credentials
        self._service = service

    def service(self):
        if self._service is None:
            self._service = build("classroom", "v1", credentials=self.credentials, cache_discovery=False)
        return self._service

    def list_courses(self, teacher_only: bool = True) -> list[dict]:
        courses = []
        page_token = None
        params: dict[str, Any] = {"courseStates": ["ACTIVE"]}
        if teacher_only:
            params["teacherId"] = "me"
        try:
            while True:
                response = self.service().courses().list(pageToken=page_token, **params).execute()
                courses.extend(response.get("courses") or [])
                page_token = response.get("nextPageToken")
                if not page_token:
                    break
        except HttpError:
            if teacher_only:
                return self.list_courses(teacher_only=False)
            raise
        if teacher_only and not courses:
            return self.list_courses(teacher_only=False)
        return courses

    def get_course(self, course_id: str) -> dict:
        return self.service().courses().get(id=course_id).execute()

    def list_coursework(self, course_id: str) -> list[dict]:
        items = []
        page_token = None
        while True:
            response = (
                self.service()
                .courses()
                .courseWork()
                .list(courseId=course_id, pageToken=page_token, courseWorkStates=["PUBLISHED"])
                .execute()
            )
            items.extend(response.get("courseWork") or [])
            page_token = response.get("nextPageToken")
            if not page_token:
                break
        return items

    def get_coursework(self, course_id: str, coursework_id: str) -> dict:
        return (
            self.service()
            .courses()
            .courseWork()
            .get(courseId=course_id, id=coursework_id)
            .execute()
        )

    def list_students(self, course_id: str) -> list[dict]:
        students = []
        page_token = None
        while True:
            response = (
                self.service()
                .courses()
                .students()
                .list(courseId=course_id, pageToken=page_token)
                .execute()
            )
            students.extend(response.get("students") or [])
            page_token = response.get("nextPageToken")
            if not page_token:
                break
        return students

    def list_student_submissions(self, course_id: str, coursework_id: str) -> list[dict]:
        submissions = []
        page_token = None
        while True:
            response = (
                self.service()
                .courses()
                .courseWork()
                .studentSubmissions()
                .list(courseId=course_id, courseWorkId=coursework_id, pageToken=page_token)
                .execute()
            )
            submissions.extend(response.get("studentSubmissions") or [])
            page_token = response.get("nextPageToken")
            if not page_token:
                break
        return submissions

    def draft_roster(self, course_id: str) -> list[RosterEntry]:
        rows = []
        for student in self.list_students(course_id):
            profile = student.get("profile") or {}
            rows.append(
                RosterEntry(
                    classroom_user_id=student.get("userId") or profile.get("id") or "",
                    student_email=profile.get("emailAddress") or "",
                    student_name=profile.get("name", {}).get("fullName") or "",
                    team_id="",
                    team_name="",
                )
            )
        return rows


def coursework_deadline_utc(item: dict) -> datetime | None:
    due_date = item.get("dueDate") or {}
    if not due_date.get("year"):
        return None
    due_time = item.get("dueTime") or {}
    return datetime(
        int(due_date["year"]),
        int(due_date["month"]),
        int(due_date["day"]),
        int(due_time.get("hours") or 0),
        int(due_time.get("minutes") or 0),
        int(due_time.get("seconds") or 0),
        tzinfo=timezone.utc,
    )


def upcoming_coursework(items: list[dict], now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    upcoming = []
    for item in items:
        if item.get("state") and item.get("state") != "PUBLISHED":
            continue
        work_type = item.get("workType") or "ASSIGNMENT"
        if work_type != "ASSIGNMENT":
            continue
        due = coursework_deadline_utc(item)
        if due is None or due <= now:
            continue
        row = dict(item)
        row["_deadline"] = due
        upcoming.append(row)
    upcoming.sort(key=lambda row: row["_deadline"])
    return upcoming


def deadline_iso_for_timezone(item: dict, tz_name: str) -> str:
    due = coursework_deadline_utc(item)
    if due is None:
        return ""
    return format_iso(due.astimezone(zone(tz_name)))


def classroom_error_message(exc: Exception) -> str:
    status = getattr(getattr(exc, "resp", None), "status", None)
    if status == 403:
        return (
            "Google refused to list assignments for this class (HTTP 403). "
            "Listing titles and due dates needs a Classroom coursework scope. "
            "Add it on the OAuth consent screen, then use Re-authorize Classroom "
            "so Google prompts again."
        )
    if status == 404:
        return "That Google Classroom class or assignment was not found."
    return str(exc)


def attachments_from_submission(raw: dict) -> list[dict]:
    assignment = raw.get("assignmentSubmission") or {}
    return assignment.get("attachments") or []


def extract_youtube_from_attachments(attachments: list[dict]) -> tuple[list[str], list[str]]:
    """Return (video_ids, invalid_urls). Prefers native youTubeVideo.id."""
    video_ids: list[str] = []
    invalid: list[str] = []
    for attachment in attachments:
        youtube = attachment.get("youTubeVideo") or {}
        native_id = youtube.get("id")
        if native_id:
            parsed = extract_video_id(native_id)
            if parsed:
                video_ids.append(parsed)
                continue
        link = (attachment.get("link") or {}).get("url") or youtube.get("alternateLink")
        if not link:
            continue
        video_id, _canonical = parse_and_canonicalize(link)
        if video_id:
            video_ids.append(video_id)
        else:
            invalid.append(link)
    # Preserve order, drop duplicates
    unique = []
    seen = set()
    for video_id in video_ids:
        if video_id not in seen:
            unique.append(video_id)
            seen.add(video_id)
    return unique, invalid


def turned_in_at(raw: dict) -> str:
    history = raw.get("submissionHistory") or []
    timestamps = []
    for entry in history:
        state = (entry.get("stateHistory") or {})
        if state.get("state") == TURNED_IN and state.get("stateTimestamp"):
            parsed = parse_iso(state["stateTimestamp"])
            if parsed:
                timestamps.append(parsed)
    if timestamps:
        return format_iso(max(timestamps))
    return raw.get("updateTime") or raw.get("creationTime") or ""


def was_reclaimed(raw: dict) -> bool:
    if raw.get("state") == RECLAIMED:
        return True
    for entry in raw.get("submissionHistory") or []:
        if (entry.get("stateHistory") or {}).get("state") == RECLAIMED:
            return True
    return False


def parse_submission(raw: dict, assignment_id: str) -> dict[str, Any]:
    attachments = attachments_from_submission(raw)
    video_ids, invalid = extract_youtube_from_attachments(attachments)
    return {
        "raw": raw,
        "assignment_id": assignment_id,
        "classroom_submission_id": raw.get("id") or "",
        "classroom_user_id": raw.get("userId") or "",
        "classroom_submission_state": raw.get("state") or "",
        "classroom_late": raw.get("late"),
        "submitted_at": turned_in_at(raw),
        "classroom_alternate_link": raw.get("alternateLink") or "",
        "video_ids": video_ids,
        "invalid_urls": invalid,
        "reclaimed": was_reclaimed(raw),
        "attachments": attachments,
    }


def map_roster(
    classroom_user_id: str,
    email: str,
    roster: list[RosterEntry],
) -> RosterEntry | None:
    for entry in roster:
        if entry.classroom_user_id and entry.classroom_user_id == classroom_user_id:
            return entry
    email_l = (email or "").lower()
    if email_l:
        for entry in roster:
            if entry.student_email.lower() == email_l:
                return entry
    return None
