"""YouTube Data API v3 observer. Never downloads video bytes."""

from __future__ import annotations

import logging
import time
from typing import Protocol

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.models import EventCode, VideoSnapshot
from app.utils import (
    canonicalize_youtube_url,
    description_hash,
    extract_video_id,
    fingerprint_payload,
    format_clock,
    parse_duration_seconds,
    tags_hash,
)

YOUTUBE_PARTS = "id,snippet,contentDetails,status,recordingDetails"
LOGGER = logging.getLogger("verifier")


class YouTubeSystemError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class VideoLookup(Protocol):
    def fetch(self, video_ids: list[str]) -> dict[str, VideoSnapshot]:
        """Return a snapshot per requested ID. Missing IDs are unavailable, not errors."""


def snapshot_from_api_item(item: dict) -> VideoSnapshot:
    snippet = item.get("snippet") or {}
    details = item.get("contentDetails") or {}
    status = item.get("status") or {}
    recording = item.get("recordingDetails") or {}
    duration = details.get("duration")
    snapshot = VideoSnapshot(
        video_id=item.get("id"),
        channel_id=snippet.get("channelId"),
        channel_title=snippet.get("channelTitle"),
        published_at=snippet.get("publishedAt"),
        recording_date=recording.get("recordingDate"),
        duration=duration,
        duration_seconds=parse_duration_seconds(duration),
        privacy_status=status.get("privacyStatus"),
        upload_status=status.get("uploadStatus"),
        license=status.get("license"),
        embeddable=status.get("embeddable"),
        made_for_kids=status.get("madeForKids"),
        caption=str(details.get("caption")) if details.get("caption") is not None else None,
        definition=details.get("definition"),
        dimension=details.get("dimension"),
        has_custom_thumbnail=details.get("hasCustomThumbnail"),
        title=snippet.get("title"),
        description_hash=description_hash(snippet.get("description")),
        tags_hash=tags_hash(snippet.get("tags")),
        etag=item.get("etag"),
        raw=item,
    )
    snapshot.fingerprint = fingerprint_payload(snapshot.fingerprint_fields())
    return snapshot


def unavailable_snapshot(video_id: str) -> VideoSnapshot:
    return VideoSnapshot(video_id=video_id, unavailable=True)


class YouTubeClient:
    def __init__(
        self,
        api_key: str | None = None,
        credentials=None,
        batch_size: int = 50,
        retry_attempts: int = 4,
        retry_delays_seconds: list[float] | None = None,
        service=None,
    ):
        self.api_key = api_key
        self.credentials = credentials
        self.batch_size = batch_size
        self.retry_attempts = retry_attempts
        self.retry_delays_seconds = retry_delays_seconds or [0, 2, 5, 15]
        self._service = service

    def service(self):
        if self._service is None:
            if self.credentials is not None:
                self._service = build("youtube", "v3", credentials=self.credentials, cache_discovery=False)
            elif self.api_key:
                self._service = build("youtube", "v3", developerKey=self.api_key, cache_discovery=False)
            else:
                raise YouTubeSystemError(
                    EventCode.API_ERROR.value,
                    "No YouTube API key or OAuth credentials configured",
                )
        return self._service

    def fetch(self, video_ids: list[str]) -> dict[str, VideoSnapshot]:
        unique = []
        seen = set()
        for video_id in video_ids:
            if video_id and video_id not in seen:
                unique.append(video_id)
                seen.add(video_id)
        results: dict[str, VideoSnapshot] = {}
        for offset in range(0, len(unique), self.batch_size):
            batch = unique[offset : offset + self.batch_size]
            payload = self._list_with_retry(batch)
            found = set()
            for item in payload.get("items") or []:
                snapshot = snapshot_from_api_item(item)
                if snapshot.video_id:
                    results[snapshot.video_id] = snapshot
                    found.add(snapshot.video_id)
            for video_id in batch:
                if video_id not in found:
                    results[video_id] = unavailable_snapshot(video_id)
        return results

    def fetch_one(self, video_id: str) -> VideoSnapshot:
        return self.fetch([video_id])[video_id]

    def _list_with_retry(self, video_ids: list[str]) -> dict:
        last_error: Exception | None = None
        attempts = max(1, self.retry_attempts)
        for attempt in range(attempts):
            delay = self.retry_delays_seconds[min(attempt, len(self.retry_delays_seconds) - 1)]
            if delay:
                LOGGER.info("Retrying YouTube videos.list after %.1fs", delay)
                time.sleep(delay)
            try:
                return (
                    self.service()
                    .videos()
                    .list(part=YOUTUBE_PARTS, id=",".join(video_ids))
                    .execute()
                )
            except HttpError as exc:
                last_error = exc
                code = getattr(exc.resp, "status", 500)
                LOGGER.warning("YouTube API HTTP %s on attempt %s", code, attempt + 1)
                if code == 403 and "quota" in str(exc).lower():
                    raise YouTubeSystemError(EventCode.API_QUOTA_ERROR.value, str(exc)) from exc
                if code in {500, 502, 503, 504} or code == 429:
                    continue
                raise YouTubeSystemError(EventCode.API_ERROR.value, str(exc)) from exc
            except OSError as exc:
                last_error = exc
                LOGGER.warning("YouTube network error on attempt %s: %s", attempt + 1, exc)
                continue
        raise YouTubeSystemError(EventCode.NETWORK_ERROR.value, str(last_error) if last_error else "retry exhausted")


def parse_and_canonicalize(url_or_id: str) -> tuple[str | None, str]:
    video_id = extract_video_id(url_or_id)
    if not video_id:
        return None, url_or_id
    return video_id, canonicalize_youtube_url(video_id)


def format_snapshot_text(snapshot: VideoSnapshot) -> str:
    if snapshot.unavailable:
        return (
            f"Video ID:        {snapshot.video_id}\n"
            "Status:          unavailable\n"
            "Note:            Video unavailable (private and deleted look the same to the API)\n"
        )
    return "\n".join(
        [
            f"Video ID:        {snapshot.video_id or ''}",
            f"Channel ID:      {snapshot.channel_id or ''}",
            f"Published:       {snapshot.published_at or ''}",
            f"Duration:        {format_clock(snapshot.duration_seconds) or snapshot.duration or ''}",
            f"Privacy:         {snapshot.privacy_status or ''}",
            f"Upload status:   {snapshot.upload_status or ''}",
            f"Title:           {snapshot.title or ''}",
            f"ETag:            {snapshot.etag or ''}",
        ]
    )
