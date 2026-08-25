from app.models import EventCode, Status
from app.verification import compare, snapshot_to_baseline_row
from tests.helpers import assignment, snapshot, submission
from app.youtube import unavailable_snapshot


def _result(current=None, extra=None, baseline_row=None, sub=None, current_snap=None, system_error=None):
    sub = sub or submission()
    snap = current_snap if current_snap is not None else (current if current is not None else snapshot())
    if current is None and current_snap is None:
        snap = snapshot()
    base = baseline_row or snapshot_to_baseline_row("DS07", sub, snapshot(), "2026-08-20T00:15:00+05:30")
    return compare(
        assignment(),
        sub,
        base,
        snap,
        "2026-08-21T10:00:00+05:30",
        extra_events=extra,
        system_error=system_error,
    )


def test_unchanged_is_green():
    result = _result(snapshot())
    assert result.status == Status.GREEN.value
    assert result.events == []


def test_title_change_is_yellow():
    result = _result(snapshot(title="DS7 Team 17 FINAL"))
    assert result.status == Status.YELLOW.value
    assert EventCode.TITLE_CHANGED.value in result.events


def test_description_change_is_yellow():
    result = _result(snapshot(description_hash="other"))
    assert result.status == Status.YELLOW.value
    assert EventCode.DESCRIPTION_CHANGED.value in result.events


def test_duration_change_beyond_tolerance_is_red():
    result = _result(snapshot(duration="PT6M31S", duration_seconds=391))
    assert result.status == Status.RED.value
    assert EventCode.DURATION_CHANGED.value in result.events
    assert "PT4M18S" in result.baseline_duration
    assert "PT6M31S" in result.current_duration


def test_one_second_duration_change_is_green():
    result = _result(snapshot(duration="PT4M19S", duration_seconds=259))
    assert result.status == Status.GREEN.value
    assert EventCode.DURATION_CHANGED.value not in result.events


def test_privacy_unlisted_to_unlisted_green():
    assert _result(snapshot(privacy_status="unlisted")).status == Status.GREEN.value


def test_privacy_unlisted_to_public_yellow():
    result = _result(snapshot(privacy_status="public"))
    assert result.status == Status.YELLOW.value
    assert EventCode.PRIVACY_CHANGED.value in result.events


def test_privacy_unlisted_to_private_red():
    result = _result(snapshot(privacy_status="private"))
    assert result.status == Status.RED.value


def test_channel_change_red():
    result = _result(snapshot(channel_id="UCother"))
    assert result.status == Status.RED.value
    assert EventCode.CHANNEL_CHANGED.value in result.events


def test_unavailable_is_red_not_deletion_claim():
    result = _result(unavailable_snapshot("AAAAAAAAAAA"))
    assert result.status == Status.RED.value
    assert EventCode.VIDEO_UNAVAILABLE.value in result.events
    assert EventCode.VIDEO_NOT_FOUND.value not in result.events
    assert "deleted" not in result.notes.lower()


def test_video_id_changed_in_classroom_is_red():
    sub = submission(video_id="BBBBBBBBBBB", youtube_url="https://www.youtube.com/watch?v=BBBBBBBBBBB")
    result = compare(
        assignment(),
        sub,
        snapshot_to_baseline_row("DS07", submission(), snapshot(), "2026-08-20T00:15:00+05:30"),
        snapshot(video_id="BBBBBBBBBBB"),
        "2026-08-21T10:00:00+05:30",
    )
    assert result.status == Status.RED.value
    assert EventCode.VIDEO_ID_CHANGED.value in result.events


def test_incomplete_baseline_duration_fill_is_not_duration_changed():
    incomplete = snapshot_to_baseline_row(
        "DS07",
        submission(),
        snapshot(upload_status="uploaded", duration=None, duration_seconds=None),
        "2026-08-20T00:15:00+05:30",
    )
    assert incomplete.is_complete() is False
    result = compare(
        assignment(),
        submission(),
        incomplete,
        snapshot(),
        "2026-08-20T00:40:00+05:30",
    )
    assert EventCode.DURATION_CHANGED.value not in result.events
    assert EventCode.BASELINE_INCOMPLETE.value in result.events


def test_duration_change_after_complete_baseline_is_red():
    result = _result(snapshot(duration="PT6M31S", duration_seconds=391))
    assert EventCode.DURATION_CHANGED.value in result.events
    assert result.status == Status.RED.value


def test_api_outage_is_error_not_red():
    result = compare(
        assignment(),
        submission(),
        snapshot_to_baseline_row("DS07", submission(), snapshot(), "2026-08-20T00:15:00+05:30"),
        None,
        "2026-08-21T10:00:00+05:30",
        system_error=EventCode.NETWORK_ERROR.value,
    )
    assert result.status == Status.ERROR.value
    assert EventCode.VIDEO_UNAVAILABLE.value not in result.events
    assert EventCode.VIDEO_NOT_FOUND.value not in result.events
