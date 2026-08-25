#!/usr/bin/env python3
"""List Google Classroom courses and coursework for the signed-in instructor."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.auth import login  # noqa: E402
from app.classroom import ClassroomClient, upcoming_coursework  # noqa: E402
from app.config import load_app_config  # noqa: E402
from app.utils import format_iso  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--course-id", help="If set, list coursework for this course")
    args = parser.parse_args()
    config = load_app_config()
    creds = login(config)
    client = ClassroomClient(creds)
    if args.course_id:
        items = upcoming_coursework(client.list_coursework(args.course_id))
        for item in items:
            due = format_iso(item.get("_deadline"))
            print(f"{item.get('id')}\t{item.get('title')}\t{due}")
        return 0
    for course in client.list_courses():
        print(f"{course.get('id')}\t{course.get('name')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
