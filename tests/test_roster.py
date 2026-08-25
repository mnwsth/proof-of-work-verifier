from app.models import RosterEntry
from tests.helpers import make_storage


def test_roster_round_trip(tmp_path):
    storage = make_storage(tmp_path)
    rows = [
        RosterEntry(
            student_email="a@school.edu",
            classroom_user_id="u1",
            team_id="T01",
            team_name="Team 01",
            student_name="Ada",
        )
    ]
    storage.save_roster("DS07", rows)
    loaded = storage.load_roster("DS07")
    assert loaded[0].team_id == "T01"
    assert loaded[0].student_email == "a@school.edu"
