from app.models import EventCode, Status
from tests.helpers import FakeYouTube, assignment, make_storage, snapshot, submission
from app.verification import Verifier
from app.config import AppConfig
from app.youtube import YouTubeSystemError
from pathlib import Path


def _verifier(tmp_path, youtube):
    storage = make_storage(tmp_path)
    storage.save_submissions("DS07", [submission()])
    config = AppConfig(data_root=str(tmp_path))
    return Verifier(config, storage, youtube, classroom=None), storage


def test_capture_baseline_then_duration_change(tmp_path):
    youtube = FakeYouTube({"AAAAAAAAAAA": snapshot()})
    verifier, storage = _verifier(tmp_path, youtube)
    verifier.capture_baseline(assignment())
    original = storage.load_baselines("DS07")[0]
    youtube.mapping["AAAAAAAAAAA"] = snapshot(duration="PT6M31S", duration_seconds=391)
    out = verifier.run_verification(assignment())
    result = out["results"][0]
    assert result.status == Status.RED.value
    assert EventCode.DURATION_CHANGED.value in result.events
    rows = storage.load_results("DS07", out["check_dir"].split("/")[-1])
    assert rows[0]["baseline_duration"] == "PT4M18S"
    assert rows[0]["current_duration"] == "PT6M31S"
    assert storage.load_baselines("DS07")[0].video_id == original.video_id
    meta = out["metadata"]
    assert meta["status"] == "completed"
    assert meta["red"] == 1


def test_repeated_verification_keeps_prior_runs(tmp_path):
    youtube = FakeYouTube({"AAAAAAAAAAA": snapshot()})
    verifier, storage = _verifier(tmp_path, youtube)
    verifier.capture_baseline(assignment())
    first = verifier.run_verification(assignment())
    second = verifier.run_verification(assignment())
    checks = [item for item in storage.list_checks("DS07") if item["kind"] == "verification"]
    assert len(checks) == 2
    assert first["check_dir"] != second["check_dir"]
    assert Path(first["check_dir"]).exists()
    assert Path(second["check_dir"]).exists()


def test_unavailable_after_retries_does_not_erase_baseline(tmp_path):
    youtube = FakeYouTube({"AAAAAAAAAAA": snapshot()})
    verifier, storage = _verifier(tmp_path, youtube)
    verifier.capture_baseline(assignment())
    youtube.mapping = {}
    out = verifier.run_verification(assignment())
    assert out["results"][0].status == Status.RED.value
    assert EventCode.VIDEO_UNAVAILABLE.value in out["results"][0].events
    assert storage.load_baselines("DS07")[0].video_id == "AAAAAAAAAAA"


def test_api_outage_marks_error_and_continues(tmp_path):
    youtube = FakeYouTube(
        {"AAAAAAAAAAA": snapshot()},
        error=YouTubeSystemError(EventCode.NETWORK_ERROR.value, "503"),
    )
    storage = make_storage(tmp_path)
    storage.save_submissions("DS07", [submission(), submission(team_id="T02", classroom_submission_id="sub2")])
    verifier = Verifier(AppConfig(data_root=str(tmp_path)), storage, FakeYouTube({"AAAAAAAAAAA": snapshot()}), None)
    verifier.capture_baseline(assignment())
    verifier.youtube = youtube
    out = verifier.run_verification(assignment())
    assert all(row.status == Status.ERROR.value for row in out["results"])
    assert out["metadata"]["api_errors"] == 2
    assert EventCode.VIDEO_UNAVAILABLE.value not in out["results"][0].events


def test_complete_incomplete_baseline_is_not_tamper(tmp_path):
    processing = snapshot(upload_status="uploaded", duration=None, duration_seconds=None)
    youtube = FakeYouTube({"AAAAAAAAAAA": processing})
    verifier, storage = _verifier(tmp_path, youtube)
    verifier.capture_baseline(assignment())
    assert storage.load_baselines("DS07")[0].is_complete() is False
    youtube.mapping["AAAAAAAAAAA"] = snapshot()
    verifier.capture_baseline(assignment())
    row = storage.load_baselines("DS07")[0]
    assert row.is_complete() is True
    assert row.duration == "PT4M18S"
    out = verifier.run_verification(assignment())
    assert EventCode.DURATION_CHANGED.value not in out["results"][0].events
    assert out["results"][0].status == Status.GREEN.value


def test_assignments_are_isolated(tmp_path):
    from tests.helpers import assignment as make_asg

    storage = make_storage(tmp_path)
    storage.create_assignment(make_asg("DS06"))
    storage.create_assignment(make_asg("DS08"))
    storage.save_submissions("DS07", [submission()])
    assert [row.team_id for row in storage.load_submissions("DS07")] == ["T01"]
    assert storage.load_submissions("DS06") == []
    assert storage.load_submissions("DS08") == []
