"""Filesystem, CSV, time, hashing, and YouTube URL helpers."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

ISO_FORMAT = "%Y-%m-%dT%H:%M:%S%z"
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
NON_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")
DURATION_RE = re.compile(
    r"^P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?$"
)


def setup_logging(log_path: Path | None = None) -> logging.Logger:
    logger = logging.getLogger("verifier")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    logger.addHandler(stream)
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    return logger


def safe_assignment_id(value: str) -> str:
    if not SAFE_ID_RE.match(value or ""):
        raise ValueError(f"Unsafe assignment identifier: {value!r}")
    return value


def assignment_id_from_title(title: str, coursework_id: str = "") -> str:
    slug = NON_SAFE_RE.sub("-", (title or "").strip()).strip("-._")
    slug = re.sub(r"-{2,}", "-", slug)[:40].strip("-._")
    if slug and slug[0].isalnum():
        return slug
    suffix = re.sub(r"[^A-Za-z0-9]", "", coursework_id)[-8:] or "ASSIGN"
    return f"A{suffix}"


def unique_assignment_id(existing_ids: list[str], title: str, coursework_id: str = "") -> str:
    taken = set(existing_ids)
    base = assignment_id_from_title(title, coursework_id)
    if base not in taken:
        return base
    suffix = re.sub(r"[^A-Za-z0-9]", "", coursework_id)[-8:] or "x"
    candidate = f"{base}-{suffix}"
    if candidate not in taken:
        return candidate
    n = 2
    while f"{candidate}-{n}" in taken:
        n += 1
    return f"{candidate}-{n}"


def zone(name: str) -> ZoneInfo:
    return ZoneInfo(name or "Asia/Kolkata")


def now_tz(tz_name: str) -> datetime:
    return datetime.now(zone(tz_name))


def format_iso(value: datetime | None) -> str:
    if value is None:
        return ""
    if value.tzinfo is None:
        raise ValueError("Naive datetime is not allowed")
    return value.isoformat(timespec="seconds")


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def check_folder_name(when: datetime) -> str:
    return when.strftime("%Y%m%d_%H%M%S")


def format_display(value: datetime | None, tz_name: str) -> str:
    if value is None:
        return ""
    local = value.astimezone(zone(tz_name))
    return local.strftime("%d %b %Y %H:%M:%S %Z")


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def atomic_write_json(path: Path, payload: object) -> None:
    atomic_write_text(path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=fieldnames,
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({key: _csv_value(row.get(key)) for key in fieldnames})
    atomic_write_text(path, buffer.getvalue())


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return [{key: value for key, value in row.items()} for row in csv.DictReader(handle)]


def _csv_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def parse_bool(value: str | bool | None) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    lowered = str(value).strip().lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    return None


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_description(value: str | None) -> str:
    if not value:
        return ""
    return "\n".join(line.rstrip() for line in value.replace("\r\n", "\n").split("\n")).strip()


def normalize_tags(tags: list[str] | None) -> str:
    if not tags:
        return ""
    cleaned = sorted({tag.strip().lower() for tag in tags if tag and tag.strip()})
    return "\n".join(cleaned)


def description_hash(value: str | None) -> str:
    return sha256_text(normalize_description(value))


def tags_hash(tags: list[str] | None) -> str:
    return sha256_text(normalize_tags(tags))


def parse_duration_seconds(value: str | None) -> int | None:
    if not value:
        return None
    match = DURATION_RE.match(value.strip())
    if not match:
        return None
    days = int(match.group("days") or 0)
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def format_clock(seconds: int | None) -> str:
    if seconds is None:
        return ""
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def canonicalize_youtube_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def extract_video_id(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip()
    if VIDEO_ID_RE.match(text):
        return text
    if "://" not in text and not text.startswith("//"):
        text = "https://" + text
    parsed = urlparse(text)
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = parsed.path or ""
    query = parse_qs(parsed.query)

    if host in {"youtu.be"}:
        candidate = path.strip("/").split("/")[0]
        return candidate if VIDEO_ID_RE.match(candidate) else None

    youtube_hosts = {
        "youtube.com",
        "m.youtube.com",
        "music.youtube.com",
        "youtube-nocookie.com",
    }
    if host not in youtube_hosts:
        return None

    if "v" in query and query["v"]:
        candidate = query["v"][0]
        return candidate if VIDEO_ID_RE.match(candidate) else None

    parts = [part for part in path.split("/") if part]
    if len(parts) >= 2 and parts[0] in {"embed", "shorts", "live", "v"}:
        candidate = parts[1]
        return candidate if VIDEO_ID_RE.match(candidate) else None
    return None


def fingerprint_payload(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256_text(encoded)
