#!/usr/bin/env python3
"""Create a Google Form and a DRAFT Classroom POW assignment (Module 1 clock)."""

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

COURSE_ID = "871535922934"
SOURCE_COURSEWORK_IDS = ["875563743786", "874768201391"]

WRITE_SCOPES = [
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.coursework.me",
    "https://www.googleapis.com/auth/classroom.coursework.students",
    "https://www.googleapis.com/auth/classroom.rosters.readonly",
    "https://www.googleapis.com/auth/classroom.profile.emails",
    "https://www.googleapis.com/auth/forms.body",
    "https://www.googleapis.com/auth/drive.file",
]

FORM_TITLE = "[POW] Module 1 Digital Clock"
ASSIGNMENT_TITLE = "[POW Submission] Module 1 Digital Clock — YouTube"
ASSIGNMENT_DESCRIPTION = """This assignment is a DRAFT until published. Only the team lead submits, once, for the whole team. Submit only through the Google Form embedded below — not as a Classroom file, a Classroom link attachment, or email.

The Google Form accepts only one response per team lead. You cannot edit or resubmit after you send it. Before you click Submit, check the Share link, the 11-character video ID, that the video is Unlisted and playable, and that it is 45–60 seconds.

Upload one Unlisted YouTube video of your complete working digital clock (Module 1 project).

https://courses.madhava.org.in/digital-electronics-course/modules/mod1/project

The video must clearly show the clock working. One person from the team must narrate while showing the circuit. Demonstrate all of the following:

1. The clock counting seconds automatically (at least 10 seconds).
2. Seconds resetting from 59 to 00.
3. Minutes incrementing when seconds reset (you may speed up the 555 for this).
4. The Set Hours button changing hours.
5. The Set Minutes button changing minutes.
6. The Reset Seconds button resetting seconds to 00.
7. A clear view of the complete circuit with all six displays.

Bonus (not required): hours resetting from 11 to 00.

Before you submit, follow these instructions.

1. The video must be 45–60 seconds.
2. The team lead’s name, or ID number and name, must be clearly visible on the side of each breadboard. Paper tape on the side of the board is fine. Do not place the breadboard on a sheet of paper with names. Videos without this will not be accepted.
3. On YouTube, set the video to Unlisted (not Private, not Public). Wait until processing has finished (the watch page plays and shows a duration).
4. Name the YouTube title:
   <TEAM-NAME>_<TEAM-LEAD-ID>_CLOCK
5. In the Form, paste the Share link (youtu.be/… or youtube.com/watch?v=…) and the 11-character video ID. Do not paste a Studio/edit URL, a playlist, a Shorts URL, or a channel page.
6. Submit well before the deadline.

After the deadline: do not edit the video in Studio (no trim, cut, blur, or audio replace), do not change privacy, do not delete the video, and do not replace the Form link with a different video.

We will record the submitted URL shortly after the deadline and later check whether that same video has changed. A private or deleted video cannot be verified."""


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
    print("Opening a Google sign-in window. Grant Forms and Classroom coursework access.")
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


def create_form(forms) -> dict:
    created = (
        forms.forms()
        .create(body={"info": {"title": FORM_TITLE, "documentTitle": FORM_TITLE}})
        .execute()
    )
    form_id = created["formId"]
    items = [
        heading(
            "Team lead only",
            "Submit once for your whole team. Use your @iitgn.ac.in Google account. "
            "Paste a Share link (youtu.be/… or youtube.com/watch?v=…), not a Studio or Shorts URL.",
            0,
        ),
        heading(
            "Digital clock video",
            "45–60 seconds. Unlisted. YouTube title: <TEAM-NAME>_<TEAM-LEAD-ID>_CLOCK. "
            "Show seconds counting, 59→00, minutes increment, Set Hours, Set Minutes, Reset Seconds, and all six displays.",
            1,
        ),
        text_question(
            "YouTube Share URL",
            "youtu.be/… or youtube.com/watch?v=…",
            2,
        ),
        text_question(
            "YouTube video ID",
            "The 11-character id from that same link (the v= value or the youtu.be path). Not the video title.",
            3,
        ),
        radio_question(
            "Privacy",
            "Only Unlisted is accepted.",
            ["Unlisted", "Public", "Private"],
            4,
        ),
        checkbox_question(
            "Confirmation",
            [
                "I am the team lead submitting for my whole team.",
                "The video is Unlisted, processed, and playable.",
                "After the deadline I will not use Studio Editor, change privacy, delete the video, or replace the link.",
            ],
            5,
        ),
    ]
    forms.forms().batchUpdate(
        formId=form_id,
        body={
            "requests": [
                {
                    "updateFormInfo": {
                        "info": {
                            "description": "ES 204 · Module 1 Digital Clock POW. Team lead only. One Unlisted YouTube video."
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
    raise SystemExit(f"Could not load a Section 1.4 assignment to copy assignees: {last_error}")


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
    responder = form.get("responderUri") or f"https://docs.google.com/forms/d/{form_id}/viewform"
    edit_url = f"https://docs.google.com/forms/d/{form_id}/edit"
    print("Form created")
    print(" edit", edit_url)
    print(" submit", responder)

    work = (
        classroom.courses()
        .courseWork()
        .create(
            courseId=COURSE_ID,
            body={
                "title": ASSIGNMENT_TITLE,
                "description": ASSIGNMENT_DESCRIPTION,
                "workType": "ASSIGNMENT",
                "state": "DRAFT",
                "topicId": source.get("topicId"),
                "dueDate": {"year": 2026, "month": 8, "day": 30},
                "dueTime": {"hours": 18, "minutes": 29},
                "maxPoints": source.get("maxPoints") or 100,
                "assigneeMode": "INDIVIDUAL_STUDENTS",
                "individualStudentsOptions": {"studentIds": student_ids},
                "submissionModificationMode": "MODIFIABLE_UNTIL_TURNED_IN",
                "materials": [
                    {
                        "link": {
                            "url": responder,
                            "title": "Module 1 Digital Clock POW YouTube submission form",
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
