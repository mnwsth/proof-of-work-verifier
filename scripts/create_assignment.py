#!/usr/bin/env python3
"""Create an assignment data directory and optional Classroom roster draft."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.auth import login  # noqa: E402
from app.classroom import ClassroomClient  # noqa: E402
from app.config import AssignmentConfig, load_app_config  # noqa: E402
from app.storage import Storage  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--assignment-id", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--course-id", default="")
    parser.add_argument("--coursework-id", default="")
    parser.add_argument("--deadline", default="")
    parser.add_argument("--timezone", default="Asia/Kolkata")
    parser.add_argument("--draft-roster", action="store_true")
    args = parser.parse_args()
    config = load_app_config()
    storage = Storage(config.data_root_path)
    assignment = AssignmentConfig(
        assignment_id=args.assignment_id,
        name=args.name,
        google_course_id=args.course_id,
        google_coursework_id=args.coursework_id,
        timezone=args.timezone,
        deadline_at=args.deadline,
    )
    path = storage.create_assignment(assignment)
    if args.draft_roster:
        if not args.course_id:
            print("--draft-roster requires --course-id", file=sys.stderr)
            return 2
        creds = login(config)
        client = ClassroomClient(creds)
        storage.save_roster(args.assignment_id, client.draft_roster(args.course_id))
        print("Drafted roster.csv — fill in team_id for each student.")
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
