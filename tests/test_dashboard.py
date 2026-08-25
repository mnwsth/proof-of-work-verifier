from fastapi.testclient import TestClient

from app.config import AppConfig
from app.main import create_app
from app.models import RosterEntry
from app.storage import Storage
from tests.helpers import assignment, submission


def test_home_lists_assignments_without_mixing(tmp_path):
    storage = Storage(tmp_path)
    for assignment_id in ["DS06", "DS07", "DS08"]:
        cfg = assignment(assignment_id)
        cfg.name = f"Assignment {assignment_id}"
        storage.create_assignment(cfg)
    storage.save_submissions("DS07", [submission()])
    app = create_app(AppConfig(data_root=str(tmp_path)))
    client = TestClient(app)
    home = client.get("/")
    assert home.status_code == 200
    assert "DS06" in home.text and "DS07" in home.text and "DS08" in home.text
    ds07 = client.get("/assignments/DS07")
    assert ds07.status_code == 200
    assert "T01" in ds07.text
    ds06 = client.get("/assignments/DS06")
    assert ds06.status_code == 200
    assert "T01" not in ds06.text


COURSEWORK = {
    "id": "cw1",
    "title": "Proof of Work 7",
    "state": "PUBLISHED",
    "workType": "ASSIGNMENT",
    "alternateLink": "https://classroom.google.com/c/c1/a/cw1",
    "dueDate": {"year": 2099, "month": 8, "day": 20},
    "dueTime": {"hours": 18, "minutes": 29},
}


class PickerClassroom:
    def list_courses(self, teacher_only=True):
        return [{"id": "c1", "name": "Digital Systems", "section": "2026"}]

    def get_course(self, course_id):
        return {"id": course_id, "name": "Digital Systems", "section": "2026"}

    def list_coursework(self, course_id):
        return [COURSEWORK]

    def get_coursework(self, course_id, coursework_id):
        return COURSEWORK

    def draft_roster(self, course_id):
        return [RosterEntry(classroom_user_id="u1", student_email="ada@x.com", student_name="Ada")]


def test_home_lists_classroom_classes(tmp_path):
    app = create_app(AppConfig(data_root=str(tmp_path)))
    app.state.classroom = PickerClassroom()
    home = TestClient(app).get("/")
    assert home.status_code == 200
    assert "Digital Systems" in home.text
    assert 'href="/classroom/c1"' in home.text


def test_course_page_lists_upcoming_and_import_creates_folder(tmp_path):
    storage = Storage(tmp_path)
    app = create_app(AppConfig(data_root=str(tmp_path), timezone="Asia/Kolkata"))
    app.state.classroom = PickerClassroom()
    client = TestClient(app)
    page = client.get("/classroom/c1")
    assert page.status_code == 200
    assert "Proof of Work 7" in page.text
    assert "Import" in page.text
    response = client.post(
        "/classroom/c1/coursework/cw1/import",
        data={"assignment_id": "DS07"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "/assignments/DS07" in response.headers["location"]
    cfg = storage.load_assignment("DS07")
    assert cfg.google_course_id == "c1"
    assert cfg.google_coursework_id == "cw1"
    assert cfg.deadline_at == "2099-08-20T23:59:00+05:30"
    roster = storage.load_roster("DS07")
    assert roster[0].student_name == "Ada"
    again = client.post(
        "/classroom/c1/coursework/cw1/import",
        data={"assignment_id": "OTHER"},
        follow_redirects=False,
    )
    assert again.status_code == 303
    assert "/assignments/DS07" in again.headers["location"]
    course = client.get("/classroom/c1")
    assert "Already imported as DS07" in course.text
    imported = client.get("/assignments/DS07?imported=1")
    assert imported.status_code == 200
    assert "Fill" in imported.text and "roster.csv" in imported.text

