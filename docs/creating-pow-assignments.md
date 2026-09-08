# Creating POW assignments

Use this when you are offering the course and need a new proof-of-work (POW) in **Google Classroom** plus a **Google Form** for Unlisted YouTube URLs.

The create scripts always make a **DRAFT** Classroom assignment. Students cannot see it until you publish. Review the Form and the Classroom text first.

## What students submit

- **Team lead only**, once, for the whole team.
- **Google Form only** — not a Classroom file, extra Classroom link, or email.
- **Unlisted** YouTube Share link (`youtu.be/…` or `youtube.com/watch?v=…`) and the **11-character video ID**.
- Every video **at least 30 seconds**.
- Name or ID on the side of the breadboard (paper tape). Videos without that are not accepted.
- After the deadline: no Studio trim/cut/blur/audio replace, no privacy change, no delete, no swapping the URL.

Late work: the late policy starts when the deadline passes and applies to the **entire team**, not only the team lead.

That prose is built in `app/pow_copy.py` (`build_pow_instructions`) and pasted **identically** into the Classroom assignment description and the Form description (and the Form’s Instructions heading). Do not write a shorter version on one surface and a longer version on the other.

The shared text currently says `@iitgn.ac.in`. Change that string (and the Form’s domain restriction in the UI) to **your** school Google domain before you run a create script for your class.

## Prerequisites

1. Setup from the [README](../README.md) and [Google API credentials](google-api-credentials.md).
2. `config.local.yaml` with `google.classroom_course_id` set to **your** course.
3. You are a teacher on that course.
4. Enable **Google Forms API** and **Google Sheets API** on the same Cloud project as Classroom.
5. A previous POW (or another individual-student assignment) whose **assignee list** you want to copy (usually the team leads). The create scripts copy `individualStudentsOptions.studentIds` from `SOURCE_COURSEWORK_IDS` in that script. **Replace those IDs** with assignments in *your* course. If this is your first POW, create one draft by hand, assign the team leads, then use that assignment’s ID as the source for later scripts.

Find course and assignment IDs:

```bash
python scripts/discover_classroom.py
python scripts/discover_classroom.py --course-id YOUR_COURSE_ID
```

Classroom URLs encode IDs in base64; the scripts and `discover_classroom.py` print the numeric/string IDs the API uses.

## How a create script works

Existing scripts (copy one when you add a new exercise):

| Script | Typical use |
|---|---|
| `scripts/create_pow_debounce_assignment.py` | One video (e.g. 2.0) |
| `scripts/create_pow_latch_assignment.py` | Two videos (e.g. 2.1) |
| `scripts/create_pow_flipflop_assignment.py` | Three videos (e.g. 2.2) |
| `scripts/create_pow_counter_assignment.py` | One video (e.g. 2.3) |
| `scripts/create_pow_register_assignment.py` | One video (e.g. 2.4) |
| `scripts/create_pow_clock_assignment.py` | Module 1 clock (older pattern) |
| `scripts/create_pow_form_assignment.py` | Section 1.4 two-video (older pattern) |

Prefer the Module 2 scripts: they call `build_pow_instructions` so Classroom and Form stay in sync.

For a new exercise:

1. Copy the closest script.
2. Set `FORM_TITLE`, `ASSIGNMENT_TITLE`, exercise URL, `VIDEOS` (title + demo bullets), `RUBRIC_TEXT`, and YouTube title suffixes (`2.5`, `2.5_V1`, …).
3. Set `SOURCE_COURSEWORK_IDS` to one or more of **your** POW assignment IDs (first match that still has assignees wins).
4. Set due date in the Classroom `create` body, or omit it and set the date when you publish.
5. Run:

```bash
python scripts/create_pow_register_assignment.py
```

The first run with Forms/Classroom **write** scopes opens a browser. Sign in as the instructor and grant access. Later runs reuse `credentials/token.json`. If you add scopes later, delete `token.json` or run a script that requests consent again.

The script prints Form **edit** and **submit** URLs and the Classroom draft id. Drafts often have no public `alternateLink`; open **Classwork → Drafts**.

## After the script (Form UI)

The Forms API cannot set everything. In the Form editor:

1. **Settings → Responses → Collect email addresses** — verified Google account (scripts set `VERIFIED`; confirm in the UI).
2. **Limit to 1 response**.
3. Restrict to your school domain if that toggle exists.
4. Optional: set a Form close date under **Published** (that close datetime is UI-only; the API can only turn accepting responses on/off).

## After the script (Classroom)

1. Confirm the description matches the Form Instructions (same `build_pow_instructions` text).
2. Confirm the Form is attached as a link.
3. Set due date and topic if the script left them empty.
4. Publish when you are ready. Do not leave “DRAFT until published” language in student-facing text after you go live unless you intend it.

## Rubric spreadsheet (optional)

If you keep planning/rubrics in a Google Sheet:

1. Put the spreadsheet ID in `config.local.yaml` under `oauth.allowed_spreadsheet_ids`. The app refuses any other spreadsheet.
2. Append rubric lines to the cell you use (do not overwrite older exercises in the same cell unless you mean to).
3. Keep scores out of the student-facing Classroom/Form rubric if that is your policy; the sheet can still hold staff-only points.

The Sheets API uses the same instructor OAuth token (spreadsheets scope).

## Shared instruction rules (do not drift)

When you change student policy, change **`app/pow_copy.py`** and recreate or patch both Classroom and Form from that string. Current required lines:

- Every video at least **30 seconds**.
- Late policy at the deadline, **whole team**.
- Classroom description **equals** Form description.

## What not to commit

- `credentials/` (OAuth client, token, YouTube API key)
- `config.local.yaml` (your course and Drive IDs)
- `data/assignments/` (rosters and submissions)

Hand a colleague the repo plus `config.local.yaml.example` and the credentials doc. They fill local config and Cloud credentials for **their** class.
