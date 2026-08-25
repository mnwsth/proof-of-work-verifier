"""Baseline capture and comparison against an immutable official baseline."""

from __future__ import annotations

import logging
from collections import defaultdict

from app.classroom import map_roster, parse_submission
from app.config import AppConfig, AssignmentConfig
from app.models import (
    BaselineRow,
    CheckMetadata,
    EventCode,
    Status,
    Submission,
    VerificationResult,
    VideoSnapshot,
)
from app.rules import describe, privacy_event_severity, status_for_events
from app.storage import BaselineExistsError, Storage
from app.utils import (
    canonicalize_youtube_url,
    fingerprint_payload,
    format_clock,
    format_iso,
    now_tz,
    parse_iso,
)
from app.youtube import YouTubeSystemError

LOGGER = logging.getLogger("verifier")
FAILURE_UPLOAD_STATES = {"failed", "rejected"}


def snapshot_to_baseline_row(
    assignment_id: str,
    submission: Submission,
    snapshot: VideoSnapshot,
    captured_at: str,
) -> BaselineRow:
    complete = snapshot.is_processed() and not snapshot.unavailable and not snapshot.error_code
    return BaselineRow(
        assignment_id=assignment_id,
        team_id=submission.team_id,
        classroom_submission_id=submission.classroom_submission_id,
        classroom_submitted_at=submission.submitted_at,
        baseline_captured_at=captured_at,
        youtube_url=submission.youtube_url or canonicalize_youtube_url(snapshot.video_id or ""),
        video_id=snapshot.video_id or submission.video_id or "",
        channel_id=snapshot.channel_id or "",
        channel_title=snapshot.channel_title or "",
        published_at=snapshot.published_at or "",
        recording_date=snapshot.recording_date or "",
        duration=snapshot.duration or "",
        duration_seconds="" if snapshot.duration_seconds is None else str(snapshot.duration_seconds),
        privacy_status=snapshot.privacy_status or "",
        upload_status=snapshot.upload_status or "",
        license=snapshot.license or "",
        embeddable="" if snapshot.embeddable is None else ("true" if snapshot.embeddable else "false"),
        made_for_kids="" if snapshot.made_for_kids is None else ("true" if snapshot.made_for_kids else "false"),
        caption=snapshot.caption or "",
        definition=snapshot.definition or "",
        dimension=snapshot.dimension or "",
        has_custom_thumbnail=""
        if snapshot.has_custom_thumbnail is None
        else ("true" if snapshot.has_custom_thumbnail else "false"),
        title=snapshot.title or "",
        description_hash=snapshot.description_hash or "",
        tags_hash=snapshot.tags_hash or "",
        etag=snapshot.etag or "",
        fingerprint=snapshot.fingerprint or fingerprint_payload(snapshot.fingerprint_fields()),
        baseline_complete="true" if complete else "false",
    )


def compare(
    assignment: AssignmentConfig,
    submission: Submission,
    baseline: BaselineRow | None,
    current: VideoSnapshot | None,
    verification_time: str,
    *,
    system_error: str | None = None,
    extra_events: list[str] | None = None,
) -> VerificationResult:
    monitoring = assignment.monitoring
    events = list(extra_events or [])
    notes: list[str] = []
    error_code = system_error or ""
    baseline_snap = baseline.snapshot() if baseline else None

    if system_error:
        events.append(system_error)
    if baseline is None:
        events.append(EventCode.MISSING_VIDEO.value)
        notes.append("No official baseline row for this team")
    if not baseline or not baseline.is_complete():
        if EventCode.BASELINE_INCOMPLETE.value not in events and baseline and not baseline.is_complete():
            events.append(EventCode.BASELINE_INCOMPLETE.value)

    if current and current.unavailable and not system_error:
        events.append(EventCode.VIDEO_UNAVAILABLE.value)

    if baseline and current and not current.unavailable and not system_error:
        if submission.video_id and baseline.video_id and submission.video_id != baseline.video_id:
            events.append(EventCode.VIDEO_ID_CHANGED.value)
            notes.append(f"Baseline video {baseline.video_id}; Classroom now {submission.video_id}")
        if current.video_id and baseline.video_id and current.video_id != baseline.video_id:
            if EventCode.VIDEO_ID_CHANGED.value not in events:
                events.append(EventCode.VIDEO_ID_CHANGED.value)

        if baseline.channel_id and current.channel_id and baseline.channel_id != current.channel_id:
            events.append(EventCode.CHANNEL_CHANGED.value)

        if baseline.is_complete() and current.duration_seconds is not None and baseline.duration_seconds != "":
            baseline_seconds = int(baseline.duration_seconds)
            delta = abs(current.duration_seconds - baseline_seconds)
            if delta > monitoring.duration_tolerance_seconds:
                events.append(EventCode.DURATION_CHANGED.value)
                notes.append(
                    f"Baseline: {format_clock(baseline_seconds)}; "
                    f"Current: {format_clock(current.duration_seconds)}"
                )

        if baseline.privacy_status and current.privacy_status and baseline.privacy_status != current.privacy_status:
            events.append(EventCode.PRIVACY_CHANGED.value)
            notes.append(f"Privacy {baseline.privacy_status} -> {current.privacy_status}")
        elif baseline.privacy_status and current.unavailable:
            events.append(EventCode.PRIVACY_CHANGED.value)

        if current.upload_status in FAILURE_UPLOAD_STATES:
            events.append(EventCode.UPLOAD_STATUS_FAILURE.value)

        if baseline.title and current.title and baseline.title != current.title:
            events.append(EventCode.TITLE_CHANGED.value)
            notes.append(f'Title "{baseline.title}" -> "{current.title}"')

        if baseline.description_hash and current.description_hash and baseline.description_hash != current.description_hash:
            events.append(EventCode.DESCRIPTION_CHANGED.value)

        if baseline.tags_hash and current.tags_hash and baseline.tags_hash != current.tags_hash:
            events.append(EventCode.TAGS_CHANGED.value)

        published = parse_iso(current.published_at)
        submitted = parse_iso(submission.submitted_at or (baseline.classroom_submitted_at if baseline else ""))
        if published and submitted and published > submitted:
            grace = 300
            if (published - submitted).total_seconds() > grace:
                events.append(EventCode.VIDEO_UPLOADED_AFTER_SUBMISSION.value)

    if submission.reclaimed and EventCode.CLASSROOM_SUBMISSION_RECLAIMED.value not in events:
        events.append(EventCode.CLASSROOM_SUBMISSION_RECLAIMED.value)

    # Deduplicate while preserving order
    unique_events = []
    seen = set()
    for event in events:
        if event not in seen:
            unique_events.append(event)
            seen.add(event)

    overrides = {}
    if EventCode.PRIVACY_CHANGED.value in unique_events:
        current_privacy = current.privacy_status if current else None
        if current and current.unavailable:
            current_privacy = None
        overrides[EventCode.PRIVACY_CHANGED.value] = privacy_event_severity(current_privacy, monitoring)

    status = status_for_events(unique_events, monitoring, overrides)
    if system_error:
        status = Status.ERROR

    video_exists = ""
    if current is not None:
        video_exists = "false" if current.unavailable else "true"

    duration_match = ""
    if baseline and current and baseline.duration_seconds != "" and current.duration_seconds is not None:
        duration_match = (
            "true"
            if abs(current.duration_seconds - int(baseline.duration_seconds))
            <= monitoring.duration_tolerance_seconds
            else "false"
        )
    channel_match = ""
    if baseline and current and baseline.channel_id and current.channel_id:
        channel_match = "true" if baseline.channel_id == current.channel_id else "false"

    return VerificationResult(
        assignment_id=assignment.assignment_id,
        team_id=submission.team_id,
        team_name=submission.team_name,
        classroom_submission_id=submission.classroom_submission_id,
        classroom_submission_time=submission.submitted_at,
        baseline_captured_at=baseline.baseline_captured_at if baseline else "",
        verification_time=verification_time,
        youtube_url=submission.youtube_url,
        baseline_video_id=baseline.video_id if baseline else "",
        current_video_id=(current.video_id if current else "") or submission.video_id,
        video_exists=video_exists,
        baseline_channel_id=baseline.channel_id if baseline else "",
            current_channel_id=current.channel_id if current and current.channel_id else "",
            channel_match=channel_match,
            baseline_published_at=baseline.published_at if baseline else "",
            current_published_at=(current.published_at if current else "") or "",
            baseline_duration=baseline.duration if baseline else "",
            current_duration=(current.duration if current else "") or "",
            duration_match=duration_match,
            baseline_privacy_status=baseline.privacy_status if baseline else "",
            current_privacy_status=(current.privacy_status if current else "") or "",
            baseline_upload_status=baseline.upload_status if baseline else "",
            current_upload_status=(current.upload_status if current else "") or "",
            baseline_title=baseline.title if baseline else "",
            current_title=(current.title if current else "") or "",
            baseline_description_hash=baseline.description_hash if baseline else "",
            current_description_hash=(current.description_hash if current else "") or "",
            baseline_tags_hash=baseline.tags_hash if baseline else "",
            current_tags_hash=(current.tags_hash if current else "") or "",
            baseline_etag=baseline.etag if baseline else "",
            current_etag=(current.etag if current else "") or "",
        status=status.value,
        event_codes=";".join(unique_events),
        error_code=error_code,
        notes="; ".join(notes),
        events=unique_events,
        baseline=baseline_snap,
        current=current,
    )


def aggregate_team_submissions(
    assignment: AssignmentConfig,
    parsed_rows: list[dict],
    roster: list,
    student_index: dict[str, dict],
    seen_at: str,
) -> list[Submission]:
    by_team: dict[str, list[dict]] = defaultdict(list)
    unmapped: list[Submission] = []
    for parsed in parsed_rows:
        user_id = parsed["classroom_user_id"]
        profile = student_index.get(user_id) or {}
        email = (profile.get("profile") or {}).get("emailAddress") or ""
        name = ((profile.get("profile") or {}).get("name") or {}).get("fullName") or email or user_id
        roster_entry = map_roster(user_id, email, roster)
        parsed["student_name"] = name
        parsed["student_email"] = email
        if roster_entry is None or not roster_entry.team_id:
            unmapped.append(
                Submission(
                    assignment_id=assignment.assignment_id,
                    team_id=user_id or "unmapped",
                    team_name="",
                    students=name,
                    classroom_user_id=user_id,
                    classroom_submission_id=parsed["classroom_submission_id"],
                    classroom_submission_state=parsed["classroom_submission_state"],
                    classroom_late=parsed["classroom_late"],
                    submitted_at=parsed["submitted_at"],
                    first_seen_at=seen_at,
                    last_seen_at=seen_at,
                    current_status=Status.RED.value,
                    event_codes=[EventCode.UNMAPPED_STUDENT.value],
                    classroom_alternate_link=parsed.get("classroom_alternate_link") or "",
                )
            )
            continue
        parsed["team_id"] = roster_entry.team_id
        parsed["team_name"] = roster_entry.team_name or roster_entry.team_id
        by_team[roster_entry.team_id].append(parsed)

    teams: list[Submission] = []
    for team_id, members in sorted(by_team.items()):
        names = [member["student_name"] for member in members]
        video_ids = []
        for member in members:
            video_ids.extend(member["video_ids"])
        unique_videos = list(dict.fromkeys(video_ids))
        events = []
        youtube_url = ""
        video_id = ""
        if any(len(member["video_ids"]) > 1 for member in members):
            events.append(EventCode.MULTIPLE_VIDEOS.value)
        if len(unique_videos) > 1:
            events.append(EventCode.TEAM_MULTIPLE_VIDEOS.value)
        elif len(unique_videos) == 1:
            video_id = unique_videos[0]
            youtube_url = canonicalize_youtube_url(video_id)
        elif any(member["invalid_urls"] for member in members):
            events.append(EventCode.INVALID_YOUTUBE_URL.value)
        else:
            turned_in = [member for member in members if member["classroom_submission_state"] == "TURNED_IN"]
            if turned_in:
                events.append(EventCode.MISSING_VIDEO.value)

        canonical = sorted(members, key=lambda item: item["submitted_at"] or "")[0]
        for member in members:
            if member["classroom_submission_state"] == "TURNED_IN":
                canonical = member
                break
        reclaimed = any(member["reclaimed"] for member in members)
        if reclaimed:
            events.append(EventCode.CLASSROOM_SUBMISSION_RECLAIMED.value)

        teams.append(
            Submission(
                assignment_id=assignment.assignment_id,
                team_id=team_id,
                team_name=members[0]["team_name"],
                students=";".join(names),
                classroom_user_id=canonical["classroom_user_id"],
                classroom_submission_id=canonical["classroom_submission_id"],
                classroom_submission_state=canonical["classroom_submission_state"],
                classroom_late=canonical["classroom_late"],
                submitted_at=canonical["submitted_at"],
                youtube_url=youtube_url,
                video_id=video_id,
                first_seen_at=seen_at,
                last_seen_at=seen_at,
                current_status="",
                classroom_alternate_link=canonical.get("classroom_alternate_link") or "",
                event_codes=events,
                reclaimed=reclaimed,
            )
        )
    return teams + unmapped


class Verifier:
    def __init__(self, config: AppConfig, storage: Storage, youtube, classroom=None):
        self.config = config
        self.storage = storage
        self.youtube = youtube
        self.classroom = classroom

    def sync_submissions(self, assignment: AssignmentConfig) -> list[Submission]:
        if self.classroom is None:
            return self.storage.load_submissions(assignment.assignment_id)
        raw_submissions = self.classroom.list_student_submissions(
            assignment.google_course_id,
            assignment.google_coursework_id,
        )
        students = []
        if hasattr(self.classroom, "list_students") and assignment.google_course_id:
            students = self.classroom.list_students(assignment.google_course_id)
        student_index = {item.get("userId"): item for item in students}
        roster = self.storage.load_roster(assignment.assignment_id)
        parsed = [parse_submission(raw, assignment.assignment_id) for raw in raw_submissions]
        now = format_iso(now_tz(assignment.timezone))
        teams = aggregate_team_submissions(assignment, parsed, roster, student_index, now)
        existing = {row.team_id: row for row in self.storage.load_submissions(assignment.assignment_id)}
        for team in teams:
            prior = existing.get(team.team_id)
            if prior:
                team.first_seen_at = prior.first_seen_at or team.first_seen_at
                team.current_status = prior.current_status
        self.storage.save_submissions(assignment.assignment_id, teams)
        LOGGER.info("Synced %s team submissions for %s", len(teams), assignment.assignment_id)
        return teams

    def _fetch_snapshots(self, video_ids: list[str]) -> dict[str, VideoSnapshot]:
        if not video_ids:
            return {}
        return self.youtube.fetch(video_ids)

    def capture_baseline(self, assignment: AssignmentConfig) -> dict:
        submissions = self.sync_submissions(assignment)
        existing = self.storage.baseline_by_team(assignment.assignment_id)
        complete_incomplete = bool(existing) and not self.storage.has_complete_baseline(assignment.assignment_id)
        if existing and self.storage.has_complete_baseline(assignment.assignment_id):
            raise BaselineExistsError("A complete baseline already exists")

        started = now_tz(assignment.timezone)
        check_dir = self.storage.create_check_dir(assignment.assignment_id, assignment.timezone, started)
        metadata = CheckMetadata(
            assignment_id=assignment.assignment_id,
            status="running",
            kind="baseline",
            started_at=format_iso(started),
            teams_expected=len(submissions),
        )
        self.storage.write_check_metadata(check_dir, metadata)
        captured_at = format_iso(started)
        video_ids = [row.video_id for row in submissions if row.video_id]
        snapshots: dict[str, VideoSnapshot] = {}
        api_errors = 0
        try:
            snapshots = self._fetch_snapshots(video_ids)
        except YouTubeSystemError as exc:
            LOGGER.warning("Baseline YouTube fetch failed: %s", exc)
            api_errors = 1
            snapshots = {}

        rows: list[BaselineRow] = []
        for submission in submissions:
            snapshot = snapshots.get(submission.video_id) if submission.video_id else None
            if snapshot is None:
                snapshot = VideoSnapshot(
                    video_id=submission.video_id or None,
                    unavailable=not bool(submission.video_id),
                    error_code=EventCode.API_ERROR.value if api_errors else None,
                )
            row = snapshot_to_baseline_row(assignment.assignment_id, submission, snapshot, captured_at)
            if complete_incomplete and submission.team_id in existing and existing[submission.team_id].is_complete():
                continue
            rows.append(row)
            self.storage.write_raw(
                check_dir,
                submission.team_id,
                snapshot.raw or {"video_id": snapshot.video_id, "unavailable": snapshot.unavailable},
            )

        self.storage.save_baselines(
            assignment.assignment_id,
            rows,
            allow_create=not existing,
            complete_incomplete=complete_incomplete,
        )
        finished = now_tz(assignment.timezone)
        metadata.status = "completed"
        metadata.completed_at = format_iso(finished)
        metadata.teams_checked = len(rows)
        metadata.successful_checks = len([row for row in rows if row.baseline_complete == "true"])
        metadata.api_errors = api_errors
        self.storage.write_check_metadata(check_dir, metadata)
        LOGGER.info("Captured baseline for %s in %s", assignment.assignment_id, check_dir.name)
        return {"check_dir": str(check_dir), "metadata": metadata.model_dump(), "rows": len(rows)}

    def run_verification(self, assignment: AssignmentConfig) -> dict:
        if not self.storage.has_any_baseline(assignment.assignment_id):
            raise RuntimeError("No baseline exists. Capture baseline first.")
        submissions = self.sync_submissions(assignment)
        baselines = self.storage.baseline_by_team(assignment.assignment_id)
        started = now_tz(assignment.timezone)
        check_dir = self.storage.create_check_dir(assignment.assignment_id, assignment.timezone, started)
        verification_time = format_iso(started)
        metadata = CheckMetadata(
            assignment_id=assignment.assignment_id,
            status="running",
            kind="verification",
            started_at=verification_time,
            teams_expected=len(submissions),
        )
        self.storage.write_check_metadata(check_dir, metadata)

        ids = []
        for submission in submissions:
            if submission.video_id:
                ids.append(submission.video_id)
            baseline = baselines.get(submission.team_id)
            if baseline and baseline.video_id:
                ids.append(baseline.video_id)

        snapshots: dict[str, VideoSnapshot] = {}
        global_error = None
        try:
            snapshots = self._fetch_snapshots(ids)
        except YouTubeSystemError as exc:
            global_error = exc.code
            LOGGER.warning("Verification YouTube fetch failed: %s", exc)

        results: list[VerificationResult] = []
        api_errors = 0
        for submission in submissions:
            baseline = baselines.get(submission.team_id)
            extra = list(submission.event_codes)
            system_error = None
            current = None
            lookup_id = submission.video_id or (baseline.video_id if baseline else "")
            if global_error:
                system_error = global_error
                api_errors += 1
            elif lookup_id:
                current = snapshots.get(lookup_id)
            result = compare(
                assignment,
                submission,
                baseline,
                current,
                verification_time,
                system_error=system_error,
                extra_events=extra,
            )
            results.append(result)
            submission.current_status = result.status
            payload = {}
            if current and current.raw:
                payload = current.raw
            elif current:
                payload = {"video_id": current.video_id, "unavailable": current.unavailable}
            if system_error:
                payload = {"error": system_error}
            self.storage.write_raw(check_dir, submission.team_id, payload)

        self.storage.save_submissions(assignment.assignment_id, submissions)
        self.storage.write_check_results(check_dir, results)
        finished = now_tz(assignment.timezone)
        metadata.status = "completed"
        metadata.completed_at = format_iso(finished)
        metadata.teams_checked = len(results)
        metadata.successful_checks = len([row for row in results if row.status != Status.ERROR.value])
        metadata.api_errors = api_errors
        metadata.green = len([row for row in results if row.status == Status.GREEN.value])
        metadata.yellow = len([row for row in results if row.status == Status.YELLOW.value])
        metadata.red = len([row for row in results if row.status == Status.RED.value])
        metadata.error = len([row for row in results if row.status == Status.ERROR.value])
        self.storage.write_check_metadata(check_dir, metadata)
        LOGGER.info("Verification %s for %s complete", check_dir.name, assignment.assignment_id)
        return {"check_dir": str(check_dir), "metadata": metadata.model_dump(), "results": results}
