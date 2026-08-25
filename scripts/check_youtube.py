#!/usr/bin/env python3
"""Fetch observable YouTube metadata for a single URL. Does not download the video."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.auth import load_api_key, load_credentials  # noqa: E402
from app.config import load_app_config  # noqa: E402
from app.utils import extract_video_id  # noqa: E402
from app.youtube import YouTubeClient, format_snapshot_text  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Look up YouTube metadata by URL or video ID")
    parser.add_argument("--url", required=True, help="YouTube URL or video ID")
    args = parser.parse_args()
    video_id = extract_video_id(args.url)
    if not video_id:
        print("INVALID_YOUTUBE_URL", file=sys.stderr)
        return 2
    config = load_app_config()
    client = YouTubeClient(
        api_key=load_api_key(config),
        credentials=load_credentials(config),
        batch_size=config.api.youtube_batch_size,
        retry_attempts=config.api.retry_attempts,
        retry_delays_seconds=config.api.retry_delays_seconds,
    )
    snapshot = client.fetch_one(video_id)
    print(format_snapshot_text(snapshot))
    return 0 if not snapshot.unavailable else 1


if __name__ == "__main__":
    raise SystemExit(main())
