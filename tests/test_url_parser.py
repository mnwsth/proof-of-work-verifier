from app.utils import extract_video_id
from app.classroom import extract_youtube_from_attachments


def test_standard_watch_url():
    assert extract_video_id("https://www.youtube.com/watch?v=AAAAAAAAAAA") == "AAAAAAAAAAA"


def test_watch_url_without_www():
    assert extract_video_id("https://youtube.com/watch?v=AAAAAAAAAAA") == "AAAAAAAAAAA"


def test_short_url():
    assert extract_video_id("https://youtu.be/AAAAAAAAAAA") == "AAAAAAAAAAA"


def test_url_with_timestamp():
    assert extract_video_id("https://www.youtube.com/watch?v=AAAAAAAAAAA&t=12s") == "AAAAAAAAAAA"


def test_url_with_si_parameter():
    assert extract_video_id("https://youtu.be/AAAAAAAAAAA?si=abc") == "AAAAAAAAAAA"


def test_shorts_url():
    assert extract_video_id("https://www.youtube.com/shorts/AAAAAAAAAAA") == "AAAAAAAAAAA"


def test_embed_url():
    assert extract_video_id("https://www.youtube.com/embed/AAAAAAAAAAA") == "AAAAAAAAAAA"


def test_nocookie_embed():
    assert extract_video_id("https://www.youtube-nocookie.com/embed/AAAAAAAAAAA") == "AAAAAAAAAAA"


def test_live_url():
    assert extract_video_id("https://www.youtube.com/live/AAAAAAAAAAA") == "AAAAAAAAAAA"


def test_watch_url_without_scheme():
    assert extract_video_id("youtube.com/watch?v=AAAAAAAAAAA") == "AAAAAAAAAAA"
    assert extract_video_id("www.youtube.com/watch?v=AAAAAAAAAAA") == "AAAAAAAAAAA"


def test_short_url_without_scheme():
    assert extract_video_id("youtu.be/AAAAAAAAAAA") == "AAAAAAAAAAA"


def test_http_watch_url():
    assert extract_video_id("http://youtube.com/watch?v=AAAAAAAAAAA") == "AAAAAAAAAAA"


def test_malformed_url():
    assert extract_video_id("https://example.com/watch?v=AAAAAAAAAAA") is None


def test_non_youtube_url():
    assert extract_video_id("https://vimeo.com/12345") is None


def test_classroom_native_youtube_id_preferred():
    attachments = [
        {
            "youTubeVideo": {
                "id": "AAAAAAAAAAA",
                "alternateLink": "https://www.youtube.com/watch?v=BBBBBBBBBBB",
            }
        }
    ]
    ids, invalid = extract_youtube_from_attachments(attachments)
    assert ids == ["AAAAAAAAAAA"]
    assert invalid == []


def test_classroom_link_attachment():
    attachments = [{"link": {"url": "https://youtu.be/AAAAAAAAAAA?t=30"}}]
    ids, invalid = extract_youtube_from_attachments(attachments)
    assert ids == ["AAAAAAAAAAA"]
    assert invalid == []
