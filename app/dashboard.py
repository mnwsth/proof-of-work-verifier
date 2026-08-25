"""Jinja dashboard routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth import AuthError, is_authenticated, login, load_api_key, load_credentials
from app.classroom import (
    ClassroomClient,
    classroom_error_message,
    deadline_iso_for_timezone,
    upcoming_coursework,
)
from app.config import AppConfig, AssignmentConfig
from app.models import EVENT_DESCRIPTIONS, Resolution
from app.rules import describe, describe_many
from app.storage import BaselineExistsError, Storage
from app.utils import (
    format_display,
    format_iso,
    now_tz,
    parse_iso,
    safe_assignment_id,
    setup_logging,
    unique_assignment_id,
)
from app.verification import Verifier
from app.youtube import YouTubeClient

LOGGER = setup_logging()
TEMPLATES = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))
router = APIRouter()


def _context(request: Request, **extra):
    config: AppConfig = request.app.state.config
    return {
        "request": request,
        "authenticated": is_authenticated(config),
        "event_descriptions": {code.value: text for code, text in EVENT_DESCRIPTIONS.items()},
        **extra,
    }


def _render(request: Request, template: str, **extra):
    return TEMPLATES.TemplateResponse(request, template, _context(request, **extra))


def _storage(request: Request) -> Storage:
    return request.app.state.storage


def _verifier(request: Request) -> Verifier:
    config: AppConfig = request.app.state.config
    youtube = request.app.state.youtube
    classroom = request.app.state.classroom
    if youtube is None:
        creds = load_credentials(config)
        api_key = load_api_key(config)
        youtube = YouTubeClient(
            api_key=api_key,
            credentials=creds if not api_key else None,
            batch_size=config.api.youtube_batch_size,
            retry_attempts=config.api.retry_attempts,
            retry_delays_seconds=config.api.retry_delays_seconds,
        )
        request.app.state.youtube = youtube
    if classroom is None:
        creds = load_credentials(config)
        if creds:
            classroom = ClassroomClient(creds)
            request.app.state.classroom = classroom
    return Verifier(config, _storage(request), youtube, classroom)


def _classroom_client(request: Request) -> ClassroomClient | None:
    existing = request.app.state.classroom
    if existing is not None:
        return existing
    config: AppConfig = request.app.state.config
    if not is_authenticated(config):
        return None
    creds = load_credentials(config)
    if not creds:
        return None
    client = ClassroomClient(creds)
    request.app.state.classroom = client
    return client


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    storage = _storage(request)
    rows = []
    for assignment_id in storage.list_assignment_ids():
        assignment = storage.load_assignment(assignment_id)
        latest = storage.latest_completed_verification(assignment_id)
        meta = (latest or {}).get("metadata") or {}
        rows.append(
            {
                "assignment": assignment,
                "teams": len(storage.load_submissions(assignment_id)),
                "green": meta.get("green", 0),
                "yellow": meta.get("yellow", 0),
                "red": meta.get("red", 0),
                "error": meta.get("error", 0),
                "latest": latest["started_at"] if latest else "",
                "latest_display": format_display(parse_iso(latest["started_at"]) if latest else None, assignment.timezone),
                "baseline_at": storage.baseline_captured_at(assignment_id),
            }
        )
    courses = []
    classroom_error = ""
    client = _classroom_client(request)
    if client is not None:
        try:
            courses = client.list_courses()
        except Exception as exc:
            LOGGER.exception("Failed to list Google Classroom courses")
            classroom_error = classroom_error_message(exc)
    return _render(
        request,
        "home.html",
        rows=rows,
        courses=courses,
        classroom_error=classroom_error,
    )


@router.get("/login")
def login_route(request: Request, force: bool = False):
    try:
        login(request.app.state.config, force=force)
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        LOGGER.exception("Google sign-in failed after the browser flow")
        raise HTTPException(
            status_code=500,
            detail="Google sign-in failed after authorization. Restart the app and try /login again.",
        ) from None
    request.app.state.classroom = None
    return RedirectResponse("/", status_code=303)


@router.get("/classroom/{course_id}", response_class=HTMLResponse)
def classroom_course(request: Request, course_id: str):
    client = _classroom_client(request)
    if client is None:
        return RedirectResponse("/", status_code=303)
    config: AppConfig = request.app.state.config
    storage = _storage(request)
    classroom_error = ""
    course = {"id": course_id, "name": course_id}
    items = []
    try:
        course = client.get_course(course_id)
        raw_items = client.list_coursework(course_id)
        for item in upcoming_coursework(raw_items):
            imported_id = storage.find_assignment_id_for_coursework(course_id, item.get("id") or "")
            items.append(
                {
                    "id": item.get("id") or "",
                    "title": item.get("title") or "(untitled)",
                    "deadline": item["_deadline"],
                    "deadline_display": format_display(item["_deadline"], config.timezone),
                    "imported_id": imported_id,
                    "suggested_id": unique_assignment_id(
                        storage.list_assignment_ids(),
                        item.get("title") or "",
                        item.get("id") or "",
                    ),
                }
            )
    except Exception as exc:
        LOGGER.exception("Failed to list Classroom coursework for %s", course_id)
        classroom_error = classroom_error_message(exc)
    return _render(
        request,
        "course.html",
        course=course,
        course_id=course_id,
        items=items,
        classroom_error=classroom_error,
        timezone=config.timezone,
    )


@router.post("/classroom/{course_id}/coursework/{coursework_id}/import")
def import_coursework(
    request: Request,
    course_id: str,
    coursework_id: str,
    assignment_id: str = Form(""),
):
    client = _classroom_client(request)
    if client is None:
        raise HTTPException(status_code=400, detail="Sign in with Google first")
    storage = _storage(request)
    existing = storage.find_assignment_id_for_coursework(course_id, coursework_id)
    if existing:
        return RedirectResponse(f"/assignments/{existing}?imported=1", status_code=303)
    try:
        item = client.get_coursework(course_id, coursework_id)
    except Exception as exc:
        LOGGER.exception("Failed to load Classroom coursework %s/%s", course_id, coursework_id)
        raise HTTPException(status_code=400, detail=classroom_error_message(exc)) from exc
    config: AppConfig = request.app.state.config
    requested_id = assignment_id.strip()
    if requested_id:
        try:
            local_id = safe_assignment_id(requested_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if local_id in storage.list_assignment_ids():
            raise HTTPException(
                status_code=400,
                detail=f"Local assignment ID {local_id} is already used. Choose another.",
            )
    else:
        local_id = unique_assignment_id(
            storage.list_assignment_ids(),
            item.get("title") or "",
            coursework_id,
        )
    assignment = AssignmentConfig(
        assignment_id=local_id,
        name=(item.get("title") or local_id).strip(),
        google_course_id=course_id,
        google_coursework_id=coursework_id,
        timezone=config.timezone,
        deadline_at=deadline_iso_for_timezone(item, config.timezone),
        classroom_alternate_link=item.get("alternateLink") or "",
    )
    storage.create_assignment(assignment)
    try:
        storage.save_roster(local_id, client.draft_roster(course_id))
    except Exception:
        LOGGER.exception("Imported %s but could not draft roster from Classroom", local_id)
    return RedirectResponse(f"/assignments/{local_id}?imported=1", status_code=303)


@router.get("/assignments/new", response_class=HTMLResponse)
def new_assignment_form(request: Request):
    return _render(request, "new_assignment.html")


@router.post("/assignments/new")
def create_assignment(
    request: Request,
    assignment_id: str = Form(...),
    name: str = Form(...),
    google_course_id: str = Form(""),
    google_coursework_id: str = Form(""),
    deadline_at: str = Form(""),
    timezone: str = Form("Asia/Kolkata"),
):
    storage = _storage(request)
    config = AssignmentConfig(
        assignment_id=assignment_id.strip(),
        name=name.strip(),
        google_course_id=google_course_id.strip(),
        google_coursework_id=google_coursework_id.strip(),
        timezone=timezone.strip() or "Asia/Kolkata",
        deadline_at=deadline_at.strip(),
    )
    storage.create_assignment(config)
    return RedirectResponse(f"/assignments/{config.assignment_id}", status_code=303)


@router.get("/assignments/{assignment_id}", response_class=HTMLResponse)
def assignment_page(request: Request, assignment_id: str, status: str = "", imported: str = ""):
    storage = _storage(request)
    assignment = storage.load_assignment(assignment_id)
    submissions = storage.load_submissions(assignment_id)
    baselines = storage.baseline_by_team(assignment_id)
    resolutions = {row.team_id: row for row in storage.load_resolutions(assignment_id)}
    latest = storage.latest_completed_verification(assignment_id)
    results = {
        row["team_id"]: row
        for row in (storage.load_results(assignment_id, latest["timestamp"]) if latest else [])
    }
    table = []
    counts = {"GREEN": 0, "YELLOW": 0, "RED": 0, "ERROR": 0}
    for submission in submissions:
        result = results.get(submission.team_id, {})
        team_status = result.get("status") or submission.current_status
        if team_status in counts:
            counts[team_status] += 1
        if status and team_status != status:
            continue
        resolution = resolutions.get(submission.team_id)
        table.append(
            {
                "submission": submission,
                "result": result,
                "status": team_status,
                "issue": describe_many(result.get("event_codes", "")),
                "resolution": resolution.decision if resolution else "",
                "last_checked": result.get("verification_time", ""),
            }
        )
    checks = storage.list_checks(assignment_id)
    incomplete = storage.incomplete_baseline_teams(assignment_id)
    has_baseline = storage.has_any_baseline(assignment_id)
    complete = storage.has_complete_baseline(assignment_id)
    baseline_at = storage.baseline_captured_at(assignment_id)
    return _render(
        request,
        "assignment.html",
        assignment=assignment,
        table=table,
        counts=counts,
        latest=latest,
        checks=checks,
        has_baseline=has_baseline,
        complete_baseline=complete,
        incomplete=incomplete,
        baseline_at=baseline_at,
        baseline_display=format_display(parse_iso(baseline_at), assignment.timezone),
        deadline_display=format_display(parse_iso(assignment.deadline_at), assignment.timezone),
        latest_display=format_display(parse_iso(latest["started_at"]) if latest else None, assignment.timezone),
        filter_status=status,
        imported=imported == "1",
        describe=describe,
    )


@router.post("/assignments/{assignment_id}/sync")
def sync_assignment(request: Request, assignment_id: str):
    assignment = _storage(request).load_assignment(assignment_id)
    _verifier(request).sync_submissions(assignment)
    return RedirectResponse(f"/assignments/{assignment_id}", status_code=303)


@router.post("/assignments/{assignment_id}/baseline")
def capture_baseline(request: Request, assignment_id: str):
    assignment = _storage(request).load_assignment(assignment_id)
    try:
        _verifier(request).capture_baseline(assignment)
    except BaselineExistsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(f"/assignments/{assignment_id}", status_code=303)


@router.post("/assignments/{assignment_id}/verify")
def run_verification(request: Request, assignment_id: str):
    assignment = _storage(request).load_assignment(assignment_id)
    _verifier(request).run_verification(assignment)
    return RedirectResponse(f"/assignments/{assignment_id}", status_code=303)


@router.get("/assignments/{assignment_id}/teams/{team_id}", response_class=HTMLResponse)
def team_page(request: Request, assignment_id: str, team_id: str):
    storage = _storage(request)
    assignment = storage.load_assignment(assignment_id)
    submissions = {row.team_id: row for row in storage.load_submissions(assignment_id)}
    submission = submissions.get(team_id)
    if submission is None:
        raise HTTPException(status_code=404, detail="Team not found")
    baseline = storage.baseline_by_team(assignment_id).get(team_id)
    latest = storage.latest_completed_verification(assignment_id)
    result = storage.load_result_for_team(assignment_id, latest["timestamp"], team_id) if latest else {}
    history = []
    for check in storage.list_checks(assignment_id):
        if check["status"] != "completed":
            continue
        row = storage.load_result_for_team(assignment_id, check["timestamp"], team_id)
        history.append({"check": check, "result": row})
    resolutions = {row.team_id: row for row in storage.load_resolutions(assignment_id)}
    return _render(
        request,
        "team.html",
        assignment=assignment,
        submission=submission,
        baseline=baseline,
        result=result or {},
        history=history,
        resolution=resolutions.get(team_id),
        describe=describe,
        describe_many=describe_many,
        baseline_display=format_display(parse_iso(baseline.baseline_captured_at if baseline else ""), assignment.timezone),
        submitted_display=format_display(parse_iso(submission.submitted_at), assignment.timezone),
        verified_display=format_display(parse_iso((result or {}).get("verification_time")), assignment.timezone),
    )


@router.post("/assignments/{assignment_id}/teams/{team_id}/resolution")
def save_resolution(
    request: Request,
    assignment_id: str,
    team_id: str,
    decision: str = Form("none"),
    penalty_points: str = Form(""),
    reason: str = Form(""),
    decided_by: str = Form(""),
):
    storage = _storage(request)
    assignment = storage.load_assignment(assignment_id)
    latest = storage.latest_completed_verification(assignment_id)
    storage.upsert_resolution(
        Resolution(
            assignment_id=assignment_id,
            team_id=team_id,
            decision=decision,
            penalty_points=penalty_points,
            reason=reason,
            decided_at=format_iso(now_tz(assignment.timezone)),
            decided_by=decided_by,
            related_check_timestamp=latest["timestamp"] if latest else "",
        )
    )
    return RedirectResponse(f"/assignments/{assignment_id}/teams/{team_id}", status_code=303)


@router.get("/assignments/{assignment_id}/export")
def export_csv(request: Request, assignment_id: str):
    path = _storage(request).write_export(assignment_id)
    return FileResponse(path, filename=f"{assignment_id}_export.csv", media_type="text/csv")
