#!/usr/bin/env python3
"""Create a Google Form and a DRAFT Classroom POW assignment (Module 2.2 flip-flops)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from app.config import load_app_config
from app.pow_copy import build_pow_instructions

COURSE_ID = "871535922934"
SOURCE_COURSEWORK_IDS = ["872540541621", "875563743786", "876544700435"]

WRITE_SCOPES = [
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.coursework.me",
    "https://www.googleapis.com/auth/classroom.coursework.students",
    "https://www.googleapis.com/auth/classroom.rosters.readonly",
    "https://www.googleapis.com/auth/classroom.profile.emails",
    "https://www.googleapis.com/auth/forms.body",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/spreadsheets",
]

FORM_TITLE = "[POW] Section 2.2 (Flip-Flops)"
ASSIGNMENT_TITLE = "[POW Submission] Section 2.2 (Flip-Flops) — YouTube (3 videos)"
VIDEOS = [
    (
        "D Latch",
        [
            "Gated SR latch (7400), 7404 inverter, Data button, and Enable button in view.",
            "Enable HIGH: Q copies D.",
            "Enable LOW: Q stays frozen when D changes.",
        ],
    ),
    (
        "D Flip-Flop",
        [
            "7474 IC, D and CLK buttons, and Q / Q' LEDs in view.",
            "Hold D = 1, tap CLK: Q turns ON.",
            "Hold D = 0, tap CLK: Q turns OFF.",
            "Hold D = 1 without tapping CLK: Q does not change.",
        ],
    ),
    (
        "T Flip-Flop",
        [
            "7474, 7486 XOR, T control, and CLK in view.",
            "T = 0: clock taps do not change Q.",
            "T = 1: clock taps toggle Q.",
        ],
    ),
]
RUBRIC_TEXT = """2.2 Video 1 — D Latch
- 7400 gated SR + 7404 inverter + Data and Enable buttons in view
- Enable HIGH: Q copies D
- Enable LOW: Q stays frozen when D changes

2.2 Video 2 — D Flip-Flop
- 7474 + D and CLK buttons + Q and Q' LEDs in view
- Hold D=1, tap CLK: Q turns ON
- Hold D=0, tap CLK: Q turns OFF
- Hold D=1 without CLK: Q does not change

2.2 Video 3 — T Flip-Flop
- 7474 + 7486 XOR + T control + CLK in view
- T=0: clock taps do not change Q
- T=1: clock taps toggle Q"""
INSTRUCTIONS = build_pow_instructions(
    section_label="Section 2.2 of Module 2",
    exercise_url="https://courses.madhava.org.in/digital-electronics-course/modules/mod2/ex2",
    videos=VIDEOS,
    rubric_text=RUBRIC_TEXT,
    youtube_title_suffixes=["2.2_V1", "2.2_V2", "2.2_V3"],
)


def granted_scopes(token_path: Path) -> set[str]:
    if not token_path.exists():
        return set()
    data = json.loads(token_path.read_text(encoding="utf-8"))
    scopes = data.get("scopes") or []
    if isinstance(scopes, str):
        scopes = scopes.split()
    return set(scopes)


def load_write_credentials(config) -> Credentials:
    token_path = config.resolve(config.oauth.token_file)
    secrets = config.resolve(config.oauth.client_secrets_file)
    if not secrets.exists():
        raise SystemExit(f"Missing OAuth client secrets at {secrets}")
    missing = [scope for scope in WRITE_SCOPES if scope not in granted_scopes(token_path)]
    if not missing and token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), WRITE_SCOPES)
        try:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                token_path.write_text(creds.to_json(), encoding="utf-8")
            if creds and creds.valid:
                return creds
        except RefreshError:
            creds = None
    print("Opening a Google sign-in window. Grant Forms, Classroom coursework, and Sheets access.")
    flow = InstalledAppFlow.from_client_secrets_file(str(secrets), WRITE_SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def text_question(title: str, description: str, index: int) -> dict:
    return {
        "createItem": {
            "item": {
                "title": title,
                "description": description,
                "questionItem": {
                    "question": {
                        "required": True,
                        "textQuestion": {"paragraph": False},
                    }
                },
            },
            "location": {"index": index},
        }
    }


def radio_question(title: str, description: str, options: list[str], index: int) -> dict:
    return {
        "createItem": {
            "item": {
                "title": title,
                "description": description,
                "questionItem": {
                    "question": {
                        "required": True,
                        "choiceQuestion": {
                            "type": "RADIO",
                            "options": [{"value": option} for option in options],
                        },
                    }
                },
            },
            "location": {"index": index},
        }
    }


def checkbox_question(title: str, options: list[str], index: int) -> dict:
    return {
        "createItem": {
            "item": {
                "title": title,
                "description": "Check every box.",
                "questionItem": {
                    "question": {
                        "required": True,
                        "choiceQuestion": {
                            "type": "CHECKBOX",
                            "options": [{"value": option} for option in options],
                        },
                    }
                },
            },
            "location": {"index": index},
        }
    }


def heading(title: str, description: str, index: int) -> dict:
    return {
        "createItem": {
            "item": {
                "title": title,
                "description": description,
                "textItem": {},
            },
            "location": {"index": index},
        }
    }


def video_block(index: int, number: int, title: str) -> list[dict]:
    return [
        heading(
            f"Video {number} — {title}",
            "",
            index,
        ),
        text_question(
            f"YouTube Share URL — Video {number}",
            "youtu.be/… or youtube.com/watch?v=…",
            index + 1,
        ),
        text_question(
            f"YouTube video ID — Video {number}",
            "The 11-character id from that same link. Must be different from the other videos.",
            index + 2,
        ),
        radio_question(
            f"Privacy — Video {number}",
            "Only Unlisted is accepted.",
            ["Unlisted", "Public", "Private"],
            index + 3,
        ),
    ]


def create_form(forms) -> dict:
    created = (
        forms.forms()
        .create(body={"info": {"title": FORM_TITLE, "documentTitle": FORM_TITLE}})
        .execute()
    )
    form_id = created["formId"]
    items = [
        heading("Instructions", INSTRUCTIONS, 0),
        *video_block(1, 1, "D Latch"),
        *video_block(5, 2, "D Flip-Flop"),
        *video_block(9, 3, "T Flip-Flop"),
        checkbox_question(
            "Confirmation",
            [
                "I am the team lead submitting for my whole team.",
                "All three videos are Unlisted, processed, and playable.",
                "After the deadline I will not use Studio Editor, change privacy, delete any video, or replace any link.",
            ],
            13,
        ),
    ]
    forms.forms().batchUpdate(
        formId=form_id,
        body={
            "requests": [
                {
                    "updateFormInfo": {
                        "info": {
                            "description": INSTRUCTIONS
                        },
                        "updateMask": "description",
                    }
                },
                {
                    "updateSettings": {
                        "settings": {"emailCollectionType": "VERIFIED"},
                        "updateMask": "emailCollectionType",
                    }
                },
                *items,
            ]
        },
    ).execute()
    return forms.forms().get(formId=form_id).execute()


def load_source(classroom) -> dict:
    last_error = None
    for coursework_id in SOURCE_COURSEWORK_IDS:
        try:
            return (
                classroom.courses()
                .courseWork()
                .get(courseId=COURSE_ID, id=coursework_id)
                .execute()
            )
        except Exception as exc:
            last_error = exc
    raise SystemExit(f"Could not load a POW assignment to copy assignees: {last_error}")


def main() -> int:
    config = load_app_config()
    creds = load_write_credentials(config)
    classroom = build("classroom", "v1", credentials=creds, cache_discovery=False)
    forms = build("forms", "v1", credentials=creds, cache_discovery=False)

    source = load_source(classroom)
    student_ids = (source.get("individualStudentsOptions") or {}).get("studentIds") or []
    if not student_ids:
        raise SystemExit("Source assignment has no individual assignees.")
    print(f"Copying {len(student_ids)} assignees from {source.get('title')}")

    form = create_form(forms)
    form_id = form["formId"]
    email_type = (form.get("settings") or {}).get("emailCollectionType")
    responder = form.get("responderUri") or f"https://docs.google.com/forms/d/{form_id}/viewform"
    edit_url = f"https://docs.google.com/forms/d/{form_id}/edit"
    print("Form created")
    print(" edit", edit_url)
    print(" submit", responder)
    print(" emailCollectionType", email_type)

    work = (
        classroom.courses()
        .courseWork()
        .create(
            courseId=COURSE_ID,
            body={
                "title": ASSIGNMENT_TITLE,
                "description": INSTRUCTIONS,
                "workType": "ASSIGNMENT",
                "state": "DRAFT",
                "topicId": source.get("topicId"),
                "dueDate": {"year": 2026, "month": 9, "day": 9},
                "dueTime": {"hours": 18, "minutes": 29},
                "assigneeMode": "INDIVIDUAL_STUDENTS",
                "individualStudentsOptions": {"studentIds": student_ids},
                "submissionModificationMode": "MODIFIABLE_UNTIL_TURNED_IN",
                "materials": [
                    {
                        "link": {
                            "url": responder,
                            "title": "Section 2.2 Flip-Flops POW YouTube submission form",
                        }
                    }
                ],
            },
        )
        .execute()
    )
    print("Draft Classroom assignment created")
    print(" id", work.get("id"))
    print(" state", work.get("state"))
    print(" due", work.get("dueDate"), work.get("dueTime"))
    print(" assignees", len((work.get("individualStudentsOptions") or {}).get("studentIds") or []))
    print(" link", work.get("alternateLink"))
    print(
        "\nIn the Form UI, also turn on Limit to 1 response and restrict to @iitgn.ac.in if those toggles are available."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
