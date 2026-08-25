from datetime import datetime, timezone

from app.classroom import parse_submission, upcoming_coursework, was_reclaimed
from app.models import RosterEntry
from app.utils import assignment_id_from_title, unique_assignment_id
from app.verification import aggregate_team_submissions
from tests.helpers import assignment


def _raw(**overrides):
    data = {
        "id": "sub1",
        "userId": "u1",
        "state": "TURNED_IN",
        "late": False,
        "updateTime": "2026-08-19T23:41:22+05:30",
        "alternateLink": "https://classroom.google.com/c/x/a/y/sub1",
        "submissionHistory": [
            {"stateHistory": {"state": "TURNED_IN", "stateTimestamp": "2026-08-19T23:41:22+05:30"}}
        ],
        "assignmentSubmission": {
            "attachments": [{"youTubeVideo": {"id": "AAAAAAAAAAA"}}]
        },
    }
    data.update(overrides)
    return data


def test_parse_native_youtube_and_turn_in_time():
    parsed = parse_submission(_raw(), "DS07")
    assert parsed["video_ids"] == ["AAAAAAAAAAA"]
    assert parsed["submitted_at"].startswith("2026-08-19T23:41:22")
    assert parsed["classroom_submission_state"] == "TURNED_IN"


def test_reclaim_detected():
    raw = _raw(
        state="RECLAIMED_BY_STUDENT",
        submissionHistory=[
            {"stateHistory": {"state": "TURNED_IN", "stateTimestamp": "2026-08-19T23:41:22+05:30"}},
            {"stateHistory": {"state": "RECLAIMED_BY_STUDENT", "stateTimestamp": "2026-08-20T01:00:00+05:30"}},
        ],
    )
    assert was_reclaimed(raw) is True
    parsed = parse_submission(raw, "DS07")
    assert parsed["reclaimed"] is True


def test_unmapped_student_fails_closed():
    parsed = parse_submission(_raw(), "DS07")
    teams = aggregate_team_submissions(assignment(), [parsed], roster=[], student_index={}, seen_at="2026-08-20T00:15:00+05:30")
    assert teams[0].event_codes == ["UNMAPPED_STUDENT"]


def test_team_multiple_videos():
    roster = [
        RosterEntry(classroom_user_id="u1", team_id="T01", team_name="Team 01", student_name="A"),
        RosterEntry(classroom_user_id="u2", team_id="T01", team_name="Team 01", student_name="B"),
    ]
    first = parse_submission(_raw(), "DS07")
    second = parse_submission(
        _raw(id="sub2", userId="u2", assignmentSubmission={"attachments": [{"youTubeVideo": {"id": "BBBBBBBBBBB"}}]}),
        "DS07",
    )
    teams = aggregate_team_submissions(
        assignment(),
        [first, second],
        roster,
        {"u1": {"profile": {"name": {"fullName": "A"}}}, "u2": {"profile": {"name": {"fullName": "B"}}}},
        "2026-08-20T00:15:00+05:30",
    )
    assert teams[0].event_codes == ["TEAM_MULTIPLE_VIDEOS"]
    assert teams[0].video_id == ""


def test_upcoming_coursework_keeps_future_assignments_only():
    now = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)
    items = [
        {
            "id": "past",
            "title": "Old",
            "state": "PUBLISHED",
            "workType": "ASSIGNMENT",
            "dueDate": {"year": 2026, "month": 8, "day": 1},
            "dueTime": {"hours": 18, "minutes": 29},
        },
        {
            "id": "future",
            "title": "Soon",
            "state": "PUBLISHED",
            "workType": "ASSIGNMENT",
            "dueDate": {"year": 2026, "month": 8, "day": 21},
            "dueTime": {"hours": 18, "minutes": 29},
        },
        {"id": "none", "title": "No due", "state": "PUBLISHED", "workType": "ASSIGNMENT"},
        {
            "id": "draft",
            "title": "Draft",
            "state": "DRAFT",
            "workType": "ASSIGNMENT",
            "dueDate": {"year": 2026, "month": 8, "day": 21},
            "dueTime": {"hours": 18, "minutes": 29},
        },
        {
            "id": "quiz",
            "title": "Quiz",
            "state": "PUBLISHED",
            "workType": "SHORT_ANSWER_QUESTION",
            "dueDate": {"year": 2026, "month": 8, "day": 21},
            "dueTime": {"hours": 18, "minutes": 29},
        },
    ]
    upcoming = upcoming_coursework(items, now=now)
    assert [item["id"] for item in upcoming] == ["future"]


def test_assignment_id_from_title_and_collision():
    assert assignment_id_from_title("Digital Systems - PoW 7") == "Digital-Systems-PoW-7"
    assert assignment_id_from_title("!!!", "abc123xyz") == "Abc123xyz"
    assert unique_assignment_id(["Digital-Systems-PoW-7"], "Digital Systems - PoW 7", "cw99") == "Digital-Systems-PoW-7-cw99"

