from app.models import EventCode
from app.youtube import YouTubeClient, YouTubeSystemError, snapshot_from_api_item, unavailable_snapshot


class FakeResponse:
    def __init__(self, items):
        self._items = items
        self.calls = 0

    def videos(self):
        return self

    def list(self, **kwargs):
        return self

    def execute(self):
        self.calls += 1
        return {"items": self._items}


def test_snapshot_from_api_item_normalizes_duration():
    item = {
        "id": "AAAAAAAAAAA",
        "etag": "e1",
        "snippet": {
            "channelId": "UC1",
            "channelTitle": "Ch",
            "publishedAt": "2026-08-19T17:55:12Z",
            "title": "Demo",
            "description": "Hello\nWorld",
            "tags": ["b", "a"],
        },
        "contentDetails": {"duration": "PT4M18S", "caption": "false", "definition": "hd", "dimension": "2d"},
        "status": {"privacyStatus": "unlisted", "uploadStatus": "processed", "embeddable": True, "madeForKids": False},
        "recordingDetails": {},
    }
    snap = snapshot_from_api_item(item)
    assert snap.duration_seconds == 258
    assert snap.privacy_status == "unlisted"
    assert snap.fingerprint


def test_missing_item_is_unavailable_not_exception():
    client = YouTubeClient(service=FakeResponse([]), retry_attempts=1, retry_delays_seconds=[0])
    results = client.fetch(["AAAAAAAAAAA"])
    assert results["AAAAAAAAAAA"].unavailable is True


def test_retries_then_system_error():
    class Boom(FakeResponse):
        def execute(self):
            self.calls += 1
            raise OSError("timeout")

    client = YouTubeClient(service=Boom([]), retry_attempts=2, retry_delays_seconds=[0, 0])
    try:
        client.fetch(["AAAAAAAAAAA"])
        assert False, "expected error"
    except YouTubeSystemError as exc:
        assert exc.code == EventCode.NETWORK_ERROR.value
