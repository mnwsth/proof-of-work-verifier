import pytest

from app.models import Resolution
from app.storage import BaselineExistsError
from app.verification import snapshot_to_baseline_row
from tests.helpers import make_storage, snapshot, submission


def test_creates_assignment_directory(tmp_path):
    storage = make_storage(tmp_path)
    path = storage.assignment_dir("DS07")
    assert (path / "assignment.yaml").exists()
    assert (path / "roster.csv").exists()
    assert (path / "baseline.csv").exists()
    assert (path / "checks").is_dir()


def test_csv_round_trip(tmp_path):
    storage = make_storage(tmp_path)
    row = snapshot_to_baseline_row("DS07", submission(), snapshot(), "2026-08-20T00:15:00+05:30")
    storage.save_baselines("DS07", [row], allow_create=True)
    loaded = storage.load_baselines("DS07")
    assert loaded[0].video_id == "AAAAAAAAAAA"
    assert loaded[0].duration == "PT4M18S"
    assert loaded[0].is_complete() is True


def test_duplicate_baseline_rejected(tmp_path):
    storage = make_storage(tmp_path)
    row = snapshot_to_baseline_row("DS07", submission(), snapshot(), "2026-08-20T00:15:00+05:30")
    storage.save_baselines("DS07", [row], allow_create=True)
    with pytest.raises(BaselineExistsError):
        storage.save_baselines("DS07", [row], allow_create=False)


def test_check_directory_not_overwritten(tmp_path):
    storage = make_storage(tmp_path)
    first = storage.create_check_dir("DS07", "Asia/Kolkata")
    storage.write_raw(first, "T01", {"ok": True})
    assert (first / "raw" / "T01.json").exists()
    second = storage.create_check_dir("DS07", "Asia/Kolkata")
    assert first != second
    assert first.exists()


def test_resolution_upsert(tmp_path):
    storage = make_storage(tmp_path)
    storage.upsert_resolution(
        Resolution(assignment_id="DS07", team_id="T01", decision="confirmed", penalty_points="5", reason="duration")
    )
    storage.upsert_resolution(
        Resolution(assignment_id="DS07", team_id="T01", decision="confirmed", penalty_points="10", reason="reviewed")
    )
    rows = storage.load_resolutions("DS07")
    assert len(rows) == 1
    assert rows[0].penalty_points == "10"


def test_find_assignment_id_for_coursework(tmp_path):
    storage = make_storage(tmp_path)
    assert storage.find_assignment_id_for_coursework("course1", "work1") == "DS07"
    assert storage.find_assignment_id_for_coursework("course1", "other") is None

