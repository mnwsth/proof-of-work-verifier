# Plan: YouTube Proof-of-Work Integrity Verifier

## 1. Objective

Build a small, instructor-side Python application that verifies whether YouTube proof-of-work videos submitted through Google Classroom appear to have been materially changed **since the official post-deadline baseline**.

The official freeze is a class-wide baseline captured about 15 minutes after the assignment deadline. Later grading-time snapshots compare only to that baseline. GREEN means no configured observable property changed since that snapshot — not that the video bytes are unchanged, and not that nothing changed between a student's Turn in and the baseline.

The application is intentionally narrow in scope:

- Google Classroom is used only to discover assignments, student/team submissions, submitted YouTube URLs, submission state, and official submission timestamps.
- YouTube is used to identify the submitted video and retrieve its current observable metadata.
- The application stores audit information on the local filesystem.
- No student video files are downloaded or stored by the application.
- No relational database is required.
- The instructor should be able to select an assignment, press a button, run a class-wide verification, and immediately see GREEN / YELLOW / RED results.

The intended scale is approximately 85 students/teams per class and approximately 15 assignments per semester.

The application must preserve a complete, human-readable audit trail for every assignment and every verification run.

---

## 2. Core Integrity Model

The system is based on the following chain of evidence:

1. Google Classroom establishes:
   - assignment identity
   - student/team identity
   - submission identity
   - official turn-in timestamp
   - submitted YouTube URL

2. The YouTube URL is reduced to the stable YouTube video ID.

3. The application captures an immutable baseline snapshot for that submitted video.

4. Future verification runs query YouTube again using the stored video ID and compare the current state to the baseline.

5. A submission is classified as:
   - GREEN: no configured integrity-relevant change detected **since the official baseline**
   - YELLOW: observable change detected, but not necessarily evidence of tampering
   - RED: material integrity issue requiring instructor review

Important limitation:

The standard YouTube Data API does not provide the verifier with a cryptographic hash of the complete underlying uploaded video bytes. Therefore the application must NOT claim to prove byte-for-byte video identity. It verifies continuity and consistency of the submitted YouTube artifact using its stable video ID plus observable metadata/state.

YouTube does not allow an uploaded video to be replaced by another upload while retaining the same video URL/video identity; a new upload receives a new URL. Existing videos can nevertheless be trimmed/cut in YouTube Studio, have blur or audio applied, have metadata/privacy/state changed, or be deleted. The submitted video ID is the primary artifact identifier.

Studio blur and audio replacement typically do **not** change duration or video ID and are not detectable via the Data API. The UI and README must document this gap. Do not oversell GREEN as proof that pixels or audio are unchanged.

Classroom “close submissions after due date” can freeze the submitted URL. It does not freeze the YouTube video. Keep video-ID and reclaim detection as a safety net even if policy says the URL cannot change.

---

## 3. MVP Scope

### Included

- Google OAuth for the instructor
- Google Classroom API integration
- YouTube Data API v3 integration
- Assignment selection
- Submission retrieval
- YouTube URL parsing
- Video ID extraction
- Post-deadline class-wide baseline capture (`CAPTURE BASELINE`)
- Assignment-scoped local filesystem storage
- Immutable baseline records, with one allowed completion of an incomplete (still-processing) duration
- Timestamped verification runs; every grading-time run is kept
- Per-team comparison against the official baseline only
- GREEN / YELLOW / RED / ERROR status
- Human-readable explanation of detected changes
- Raw YouTube API response snapshots
- Simple web dashboard
- Distinct `CAPTURE BASELINE` and `RUN VERIFICATION` actions
- Assignment-level and team-level detail views, with baseline time vs verification time labeled
- Instructor resolution + optional penalty fields (local only; no Classroom grade write)
- Roster/team mapping and native Classroom `youTubeVideo.id` extraction
- CSV export including resolution/penalty columns
- Retry handling for transient API failures
- Student/instructor assignment brief: unlisted, no Studio Editor after deadline, do not delete/private

### Explicitly excluded from MVP

- Storing/downloading full videos
- Video-content AI analysis
- OCR/facial recognition
- Automatic cheating determinations
- Student login to the verifier
- Students authorizing access to their YouTube accounts
- Automated editing of YouTube videos
- Google Classroom grade modification
- Google Classroom add-on integration
- PostgreSQL/relational database
- Full cloud deployment requirement
- Byte-level hashing of YouTube-transcoded video content

---

## 4. Preferred Technology Stack

Use a simple Python application.

Recommended:

- Python 3.12+
- FastAPI for backend/web application
- Uvicorn for development server
- Jinja2 + HTML/CSS/vanilla JavaScript for the dashboard, unless a lightweight frontend framework materially simplifies implementation
- `google-api-python-client`
- `google-auth`
- `google-auth-oauthlib`
- `pydantic`
- `PyYAML`
- Python standard library `csv`, `json`, `hashlib`, `pathlib`, `datetime`, `zoneinfo`, `logging`

Do not introduce unnecessary infrastructure.

The application should work locally first, for example:

```bash
python -m app
```

or:

```bash
uvicorn app.main:app --reload
```

The system may later be deployed to Google Cloud Run, but local operation is the MVP target.

---

## 5. Filesystem Architecture

Use the filesystem as persistent storage. Do not use a database.

Recommended root layout:

```text
proof_of_work_verifier/
├── README.md
├── requirements.txt
├── .gitignore
├── config.yaml
├── credentials/                 # never commit; local secrets only
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── classroom.py
│   ├── youtube.py
│   ├── storage.py
│   ├── verification.py
│   ├── models.py
│   ├── rules.py
│   ├── dashboard.py
│   ├── auth.py
│   └── utils.py
├── data/
│   └── assignments/
│       ├── DS01/
│       │   ├── assignment.yaml
│       │   ├── roster.csv
│       │   ├── submissions.csv
│       │   ├── baseline.csv
│       │   ├── resolutions.csv
│       │   └── checks/
│       │       ├── 20260820_094215/
│       │       │   ├── results.csv
│       │       │   ├── metadata.json
│       │       │   └── raw/
│       │       │       ├── T01.json
│       │       │       ├── T02.json
│       │       │       └── ...
│       │       └── 20260821_101030/
│       │           ├── results.csv
│       │           ├── metadata.json
│       │           └── raw/
│       ├── DS02/
│       └── ...
└── logs/
    └── verifier.log
```

Each assignment directory must be self-contained enough to archive independently.

For example, `data/assignments/DS07/` should contain all information necessary to understand what was submitted, what baseline was captured, and what each later verification run observed.

---

## 6. Assignment Configuration

Each assignment gets an `assignment.yaml`.

Example:

```yaml
assignment_id: DS07
name: "Digital Systems - Proof of Work 7"
google_course_id: "123456789"
google_coursework_id: "987654321"
timezone: "Asia/Kolkata"
deadline_at: "2026-08-20T23:59:00+05:30"
baseline_delay_after_deadline: "PT15M"
expected_artifact: "youtube"

monitoring:
  enabled: true
  duration_tolerance_seconds: 2
  duration_change: critical
  channel_change: critical
  privacy_change_to_private: critical
  privacy_change_to_public: warning
  title_change: warning
  description_change: warning
  tags_change: info
  publication_time_anomaly: warning
  upload_status_failure: critical

ui:
  show_raw_values: true
```

The application should be able to create this file automatically when the instructor first adds/imports an assignment.

The assignment directory name should be stable and filesystem-safe, e.g. `DS07`, while the Google Classroom coursework ID remains the authoritative external identifier.

---

## 7. Submission Retrieval from Google Classroom

Implement a Classroom adapter with functions conceptually equivalent to:

```python
list_courses()
list_coursework(course_id)
list_student_submissions(course_id, coursework_id)
get_student_submission(course_id, coursework_id, submission_id)
```

For each submission, retrieve:

- Google Classroom submission ID
- student identity (`userId`, profile name/email when the roster scope allows)
- mapped `team_id` / `team_name` from `roster.csv` (Classroom is per-student; teams are not native)
- submission state
- late status, if exposed
- submission/update timestamps
- `submissionHistory` (`TURNED_IN`, `RECLAIMED_BY_STUDENT`, later `TURNED_IN`)
- attachments, preferring the native `youTubeVideo.id` when present, otherwise parsing `link.url`

The application should prefer the official Classroom turn-in time rather than inferring submission time from YouTube.

Use the Classroom submission as the authoritative source for the assignment submission timestamp.

Only submissions in the appropriate turned-in state should normally be considered final artifacts.

If a submission is reclaimed or the attached YouTube video ID changes, record that fact and flag `CLASSROOM_SUBMISSION_RECLAIMED` and/or `VIDEO_ID_CHANGED` even if course policy says the URL cannot change. Policy is not a substitute for the check.

If several teammates attach different YouTube IDs, flag `TEAM_MULTIPLE_VIDEOS` (RED) and do not silently pick a canonical artifact. Baseline for that team waits until the instructor selects one submission or records an exception.

---

## 8. YouTube URL Extraction

The application must support at least:

```text
https://www.youtube.com/watch?v=VIDEO_ID
https://youtube.com/watch?v=VIDEO_ID
https://youtu.be/VIDEO_ID
https://www.youtube.com/shorts/VIDEO_ID
https://www.youtube.com/embed/VIDEO_ID
https://www.youtube-nocookie.com/embed/VIDEO_ID
https://www.youtube.com/live/VIDEO_ID
```

Prefer Classroom's first-class `youTubeVideo.id` over parsing a URL string when both exist.

It should tolerate extra query parameters such as `t=` and `si=`.

Canonicalize the URL to:

```text
https://www.youtube.com/watch?v=<VIDEO_ID>
```

Never use the title or URL string as the artifact identity. The stable video ID is the identity.

If the submitted attachment is not a valid YouTube URL, record a submission-level error:

```text
INVALID_YOUTUBE_URL
```

If several YouTube attachments are present on one submission:

```text
MULTIPLE_VIDEOS
```

Do not guess which one is canonical.

---

## 8.1 Roster: `roster.csv`

Classroom submissions are per student. Map them to teams with an assignment-local roster:

```text
data/assignments/<ASSIGNMENT_ID>/roster.csv
```

Columns:

```text
student_email
classroom_user_id
team_id
team_name
student_name
```

The application can draft this from the Classroom roster and let the instructor fill `team_id`. Verification should fail closed for unmapped students (`UNMAPPED_STUDENT`) rather than inventing a team.

---

## 9. Submission Record: `submissions.csv`

One row per student/team submission.

Recommended columns:

```text
assignment_id
team_id
team_name
students
classroom_submission_id
classroom_submission_state
classroom_late
submitted_at
youtube_url
video_id
first_seen_at
last_seen_at
current_status
```

Example:

```csv
assignment_id,team_id,team_name,students,classroom_submission_id,classroom_submission_state,classroom_late,submitted_at,youtube_url,video_id,first_seen_at,last_seen_at,current_status
DS07,T01,Team 01,"A;B;C",abc123,TURNED_IN,false,2026-08-19T23:41:22+05:30,https://www.youtube.com/watch?v=ABC123,ABC123,2026-08-19T23:42:01+05:30,2026-08-20T09:42:15+05:30,GREEN
```

When a new Classroom submission is observed, update or add this row.

Do not use `submissions.csv` as the historical audit log. Historical verification state belongs in the timestamped check directories.

---

## 10. Baseline Storage

Each assignment must have exactly one baseline record per accepted submission/artifact.

Store in:

```text
data/assignments/<ASSIGNMENT_ID>/baseline.csv
```

Recommended fields:

```text
assignment_id
team_id
classroom_submission_id
classroom_submitted_at
baseline_captured_at
youtube_url
video_id
channel_id
channel_title
published_at
recording_date
duration
duration_seconds
privacy_status
upload_status
license
embeddable
made_for_kids
caption
definition
dimension
has_custom_thumbnail
title
description_hash
tags_hash
etag
fingerprint
baseline_complete
```

`baseline_complete` is false until `uploadStatus=processed` and `duration` is present. Completing an incomplete baseline (filling duration once when processing finishes) is allowed and is **not** a tamper event. Any later duration change is `DURATION_CHANGED`.

The baseline is evidence and must be treated as immutable after it is complete.

Never silently overwrite an existing baseline.

If an instructor explicitly approves a replacement video, preserve the original baseline and record the replacement as an explicit event/resolution. Do not rewrite history.

---

## 11. Baseline Timing

The official MVP freeze is **not** each student's Turn in time and **not** “sometime the next day.”

Operational workflow:

1. Students submit YouTube URLs through Classroom. Prefer locking further Classroom attachment changes after the deadline.
2. About **15 minutes after the deadline**, the instructor presses `CAPTURE BASELINE` once for the assignment. This is the official class-wide baseline.
3. While grading, staff press `RUN VERIFICATION` as often as they like. Each run is a new immutable check directory. Every run compares to the official baseline only.
4. High fidelity means: detect whether configured observable properties changed **since that first post-deadline snapshot**.

Edits that were already processed before the baseline are out of scope by design.

The UI must clearly distinguish, on every assignment and team view:

- official Classroom submission / turn-in time
- assignment deadline
- **baseline capture time** (the freeze)
- verification time

Do not present GREEN as “unchanged since Turn in.” Present it as “no configured change since baseline captured at …”

YouTube Studio trims can take 30–60 minutes to re-render. A trim started before the snapshot may first become visible during a later grading run. Show baseline time vs current duration; do not claim the student edited “during grading.”

Last-second uploads may still be processing at +15 minutes. Do not freeze duration until `uploadStatus=processed`. Mark those rows `baseline_incomplete` and complete duration once when processing finishes.

---

## 12. YouTube Metadata to Capture

Use YouTube Data API v3 `videos.list` with the required `id` and only the parts actually needed.

At minimum capture:

### Identity

- `id`
- `snippet.channelId`

### Time

- `snippet.publishedAt`
- `recordingDetails.recordingDate` if available

### Video characteristics

- `contentDetails.duration`
- `contentDetails.definition` / `contentDetails.dimension` if present
- `contentDetails.caption`
- `contentDetails.hasCustomThumbnail` if present

Store these on the snapshot. Do not treat caption or thumbnail changes as RED unless a later config rule says so. They are cheap extra signals, not content proof.

### State

- `status.privacyStatus`
- `status.uploadStatus`
- `status.license`
- `status.embeddable`
- `status.madeForKids`

### Metadata

- `snippet.title`
- `snippet.description`
- tags if returned/available under the chosen API parts

### API representation

- top-level `etag`

Do not use view counts, likes, comments, etc. as integrity signals.

---

## 13. Raw YouTube Snapshots

Every baseline and every verification run should retain the raw or normalized relevant YouTube API response for each checked team.

For each check:

```text
data/assignments/DS07/checks/20260820_094215/raw/T01.json
```

The JSON should contain the exact API payload used for that check, or a faithful normalized subset if storing the entire response is undesirable.

Preserving raw observations is strongly recommended because it makes later debugging/audit possible.

---

## 14. Verification Run Architecture

Every press of the dashboard's `RUN VERIFICATION` button creates a new immutable check directory:

```text
checks/<timestamp>/
├── results.csv
├── metadata.json
└── raw/
```

Timestamp format:

```text
YYYYMMDD_HHMMSS
```

Use the assignment-configured timezone for display and folder naming.

Example:

```text
checks/20260820_094215/
```

This timestamp is the runtime/start time of the verification run, not the submission time.

Never overwrite a previous check directory.

---

## 15. `checks/<timestamp>/metadata.json`

Recommended structure:

```json
{
  "assignment_id": "DS07",
  "started_at": "2026-08-20T09:42:15+05:30",
  "completed_at": "2026-08-20T09:43:02+05:30",
  "teams_expected": 85,
  "teams_checked": 85,
  "successful_checks": 84,
  "api_errors": 1,
  "green": 78,
  "yellow": 5,
  "red": 2
}
```

The metadata file is a summary of the run and is not a substitute for `results.csv`.

---

## 16. `checks/<timestamp>/results.csv`

One row per team/submission checked in that run.

Recommended columns:

```text
assignment_id
team_id
team_name
classroom_submission_id
classroom_submission_time
baseline_captured_at
verification_time
youtube_url
baseline_video_id
current_video_id
video_exists
baseline_channel_id
current_channel_id
channel_match
baseline_published_at
current_published_at
baseline_duration
current_duration
duration_match
baseline_privacy_status
current_privacy_status
baseline_upload_status
current_upload_status
baseline_title
current_title
baseline_description_hash
current_description_hash
baseline_tags_hash
current_tags_hash
baseline_etag
current_etag
status
event_codes
error_code
notes
```

Example:

```csv
assignment_id,team_id,team_name,verification_time,youtube_url,baseline_video_id,current_video_id,video_exists,channel_match,baseline_duration,current_duration,baseline_privacy_status,current_privacy_status,status,event_codes
DS07,T01,Team 01,2026-08-20T09:42:15+05:30,https://youtu.be/ABC123,ABC123,ABC123,true,true,PT4M12S,PT4M12S,unlisted,unlisted,GREEN,
DS07,T02,Team 02,2026-08-20T09:42:16+05:30,https://youtu.be/DEF456,DEF456,DEF456,true,true,PT4M18S,PT6M31S,unlisted,unlisted,RED,DURATION_CHANGED
```

Do not modify older `results.csv` files.

---

## 17. Verification Checks

Implement the following checks in the MVP.

### 17.1 Submitted Video ID

Compare the current YouTube video ID associated with the Classroom submission against the baseline video ID.

Keep this check even if course policy says the submitted URL cannot change.

If the Classroom attachment now references another video:

```text
VIDEO_ID_CHANGED
```

Severity: RED.

Do not silently replace the baseline.

---

### 17.2 Video Existence

Query YouTube by the baseline/current video ID.

If the video is confirmed unavailable after retry handling (empty `items`; YouTube does not distinguish private from deleted for non-owners):

```text
VIDEO_UNAVAILABLE
```

Severity: RED.

UI copy: “Video unavailable” / “Current artifact is inaccessible.” Do not assert that the student deleted the video.

`VIDEO_NOT_FOUND` may be kept as an internal alias but must not be shown as a confident deletion finding.

Do not classify transient network/API failures as unavailability.

---

### 17.3 Channel ID

Compare baseline and current channel ID.

If changed:

```text
CHANNEL_CHANGED
```

Severity: RED.

Do not claim that this alone proves misconduct; it is an integrity issue requiring review.

---

### 17.4 Duration

Parse ISO 8601 durations to seconds. Compare with a configurable tolerance (default **2 seconds**). Record both raw ISO-8601 strings and the integer seconds used for comparison.

If the absolute difference exceeds tolerance:

```text
DURATION_CHANGED
```

Recommended severity: RED.

Example:

```text
Baseline: 00:04:18
Current:  00:06:31
```

Do not use exact string equality of `PT4M18S` vs `PT258S` as the comparison. Do not treat a 1-second YouTube rounding discrepancy as RED.

If baseline duration is still missing because the video was processing, do not emit `DURATION_CHANGED`; keep `BASELINE_INCOMPLETE` until duration is filled once.

---

### 17.5 Privacy Status

Expected baseline is normally `unlisted`.

Rules:

```text
unlisted -> unlisted    GREEN
unlisted -> public      YELLOW
unlisted -> private     RED
unlisted -> unavailable RED
```

Make these rules configurable.

---

### 17.6 Upload/Processing Status

If the final observed video has a failure/rejection state:

```text
UPLOAD_STATUS_FAILURE
```

Severity: RED.

Transient processing should not generate a tampering event.

---

### 17.7 Published/Upload Timestamp

Store baseline `publishedAt` and current `publishedAt`.

Compare the video publication/upload timestamp to Classroom submission time.

If the upload/publish timestamp is materially after the Classroom submission:

```text
VIDEO_UPLOADED_AFTER_SUBMISSION
```

Severity: YELLOW.

Do not automatically mark RED because timestamp semantics and YouTube processing behavior need cautious interpretation.

---

### 17.8 Title

If title changes:

```text
TITLE_CHANGED
```

Severity: YELLOW.

Display before/after values.

---

### 17.9 Description

Normalize description and calculate SHA-256.

If the normalized hash changes:

```text
DESCRIPTION_CHANGED
```

Severity: YELLOW.

Display a concise before/after indication; avoid unnecessarily dumping large descriptions into the dashboard.

---

### 17.10 Tags

Normalize tags deterministically and calculate a hash.

If changed:

```text
TAGS_CHANGED
```

Severity: INFO.

---

### 17.11 ETag

Record baseline and current ETag.

An ETag change alone must NOT produce RED.

Treat ETag as a signal to compare relevant fields.

Example:

```text
ETag changed
Title changed
Duration unchanged
Privacy unchanged
```

Result: YELLOW due to `TITLE_CHANGED`.

---

## 18. Status Rules

Overall result for a team is derived from the highest-severity active event.

Recommended precedence:

```text
RED > YELLOW > GREEN
```

Informational events may be recorded without changing overall status.

Examples:

- no changes since baseline -> GREEN
- title changed -> YELLOW
- title changed + description changed -> YELLOW
- duration changed beyond tolerance -> RED
- video unavailable (private or deleted) -> RED
- Classroom URL points to a different YouTube video -> RED
- API request failed after retries -> SYSTEM ERROR / UNKNOWN, not RED

Use a separate machine-readable status for system failures, e.g. `ERROR`, so an API outage is not confused with an integrity issue.

---

## 19. Event Codes

Use stable machine-readable event codes.

Minimum set:

```text
INVALID_YOUTUBE_URL
MISSING_VIDEO
MULTIPLE_VIDEOS
TEAM_MULTIPLE_VIDEOS
UNMAPPED_STUDENT
VIDEO_ID_CHANGED
VIDEO_UNAVAILABLE
VIDEO_NOT_FOUND
CHANNEL_CHANGED
DURATION_CHANGED
PRIVACY_CHANGED
UPLOAD_STATUS_FAILURE
VIDEO_UPLOADED_AFTER_SUBMISSION
TITLE_CHANGED
DESCRIPTION_CHANGED
TAGS_CHANGED
CLASSROOM_SUBMISSION_RECLAIMED
BASELINE_INCOMPLETE
API_ERROR
API_QUOTA_ERROR
NETWORK_ERROR
```

The UI should display human-friendly descriptions for these codes.

---

## 20. System Error Handling

Distinguish:

### Genuine artifact problem

Examples:

- `VIDEO_UNAVAILABLE`
- `VIDEO_ID_CHANGED`
- `CHANNEL_CHANGED`
- `DURATION_CHANGED`

### System/API problem

Examples:

- HTTP 500
- HTTP 502
- HTTP 503
- timeout
- API quota exhaustion
- temporary auth failure

System/API problems must not automatically produce a RED integrity result.

Implement exponential-backoff retries, for example:

```text
attempt 1: immediate
attempt 2: +30 sec
attempt 3: +2 min
attempt 4: +10 min
```

For an on-demand run, it is acceptable to return `ERROR` after retry exhaustion and allow the instructor to rerun.

---

## 21. YouTube Quota Management

Use `videos.list` by explicit video IDs. Do not use YouTube search.

Batch IDs whenever practical.

Do not perform one expensive search per student.

Cache within a single verification run so each video ID is fetched only as necessary.

The application should expose quota/API failures in the run metadata.

---

## 22. Baseline Immutability

The application must treat `baseline.csv` as immutable once a baseline row has been established.

Recommended implementation:

- load existing baseline;
- refuse accidental duplicate baseline creation;
- require explicit `--force-baseline` or a separate instructor action to create a replacement baseline;
- if replacing is explicitly approved, preserve the old baseline in an archive/event record.

Never overwrite evidence silently.

---

## 23. Replacement Approval

If the instructor legitimately allows a student/team to replace a video:

1. Keep the original baseline.
2. Record a `VIDEO_ID_CHANGED` event.
3. Record instructor approval.
4. Record old video ID and new video ID.
5. Record approval timestamp and reason.
6. Establish a new accepted artifact baseline only through an explicit action.
7. Preserve the old baseline and event history.

This is not required for the first prototype but the data model should not make it impossible.

---

## 24. Dashboard Requirements

The dashboard should have a simple navigation structure:

```text
Assignments
  |
  +-- Assignment DS01
  +-- Assignment DS02
  +-- ...
```

Assignment page:

```text
Digital Systems - Proof of Work 7

Teams: 85
GREEN: 78
YELLOW: 5
RED: 2
ERROR: 0

Last verification: 20 Aug 2026 09:42:15 IST
Baseline captured: 20 Aug 2026 00:15:00 IST
Deadline: 19 Aug 2026 23:59:00 IST

GREEN means no configured change since the baseline above.

[ CAPTURE BASELINE ]
[ RUN VERIFICATION ]
```

Below that, show a filterable table.

---

## 25. Assignment Dashboard Table

Columns:

```text
Team
Students
Submitted At
YouTube Video
Status
Issue
Resolution
Last Checked
```

Example:

| Team | Submitted | Video | Status | Issue |
|---|---|---|---|---|
| T01 | 23:41 | Open | GREEN | - |
| T02 | 23:44 | Open | RED | Duration changed |
| T03 | 23:49 | Open | YELLOW | Title changed |
| T04 | 23:52 | Open | RED | Video unavailable |

Clicking a team opens a detail page/modal.

---

## 26. Team Detail View

Display:

### Submission

- Team
- Students
- Classroom submission ID
- official submission time
- YouTube URL

### Baseline

- baseline capture time
- video ID
- channel ID
- publishedAt
- duration
- privacy
- title

### Current

- verification time
- current video ID
- current channel ID
- current duration
- current privacy
- current title

### Difference

Human-readable before/after comparison.

### Links

- Open YouTube
- Open Classroom

### Audit trail

List previous verification timestamps and resulting statuses. Never overwrite or hide an earlier run.

### Instructor resolution (local only)

On the team detail view, staff may record:

- decision: `none` | `ignore` | `confirmed` | `exception`
- optional `penalty_points`
- reason
- `decided_at`, `decided_by`

Store in `resolutions.csv`. Do not write Google Classroom grades. Export these fields with the assignment CSV so they can be applied in the gradebook by hand.

---

## 27. Capture Baseline and Run Verification

### Capture Baseline

When the instructor clicks `CAPTURE BASELINE` (intended ~15 minutes after deadline):

1. Refuse if a complete class baseline already exists, unless this is only filling `baseline_incomplete` rows.
2. Sync current Classroom submissions and roster mapping.
3. Resolve YouTube IDs (native attachment ID first).
4. Query YouTube in batches.
5. Write `baseline.csv` and a check directory that records the baseline snapshots (raw JSON included).
6. Mark rows still processing as `baseline_incomplete`.
7. Do not treat this run as a comparison against a prior baseline.

A later explicit action may complete incomplete duration fields once. That is not a replacement baseline.

### Run Verification

When staff click `RUN VERIFICATION` (during grading, as often as needed):

1. Determine selected assignment.
2. Refuse to run comparison if no official baseline exists.
3. Create new timestamp using configured timezone.
4. Create new check directory. Never overwrite a previous one.
5. Retrieve current Classroom submissions.
6. Parse/resolve each YouTube video.
7. Query YouTube in batches.
8. Compare current state against the immutable official baseline only.
9. Produce per-team results.
10. Write `results.csv`.
11. Write `metadata.json`.
12. Write raw API JSON files.
13. Update the dashboard to point to this latest run.
14. Leave prior runs and the baseline untouched.

If one team fails, continue processing the others.

The run should report partial failures without aborting the entire assignment.

---

## 28. Latest Check Selection

The dashboard should discover the latest completed verification by examining the check directories under:

```text
data/assignments/<ASSIGNMENT_ID>/checks/
```

The latest timestamped completed run should be shown as `Latest Verification`.

Do not infer the latest run from filesystem creation time alone; use the timestamp embedded in the directory name and/or `metadata.json`.

If a run directory exists but `metadata.json` indicates the run was interrupted, mark it incomplete rather than presenting it as a successful check.

---

## 29. Assignment Summary Across the Semester

The application may provide a home page with all assignments:

| Assignment | Teams | Green | Yellow | Red | Latest Check |
|---|---:|---:|---:|---:|---|
| DS01 | 85 | 80 | 4 | 1 | Sep 02 |
| DS02 | 85 | 82 | 3 | 0 | Sep 06 |
| DS03 | 84 | 79 | 4 | 1 | Sep 12 |

This page may be generated dynamically from the assignment directories and latest check files.

No cross-assignment database is necessary.

---

## 30. CSV Design Principles

All CSV files must:

- use UTF-8 encoding;
- include a header row;
- use RFC-compatible CSV quoting;
- use ISO 8601 timestamps;
- use deterministic column order;
- avoid locale-dependent date formats;
- use boolean values consistently (`true`/`false`);
- use empty values rather than ambiguous strings such as `N/A` where practical.

The application should use Python's standard `csv` module rather than hand-building CSV strings.

---

## 31. Timestamp Requirements

Use timezone-aware datetimes everywhere.

Internally, ISO 8601 is preferred.

Recommended stored format:

```text
2026-08-20T09:42:15+05:30
```

The application should consistently use `Asia/Kolkata` by default.

Do not use naive local datetime objects.

---

## 32. Concurrency and File Safety

The application is expected to be used by one instructor/operator at a time, so no complex concurrency architecture is required.

However:

- create temporary files when writing important outputs;
- write the completed file atomically using rename/replace;
- never leave a partially written `results.csv` that looks complete;
- create a `metadata.json` status indicating `running`, `completed`, or `failed`.

Example:

```json
{
  "status": "running",
  "started_at": "..."
}
```

then at successful completion:

```json
{
  "status": "completed",
  "started_at": "...",
  "completed_at": "..."
}
```

---

## 33. Logging

Use a normal application log:

```text
logs/verifier.log
```

Log:

- application startup/shutdown
- authentication events
- assignment syncs
- verification start/end
- per-team errors
- API failures
- retry events
- files written

Do NOT log OAuth access tokens or refresh tokens.

---

## 34. Configuration

Global `config.yaml` should contain only non-secret settings.

Example:

```yaml
timezone: Asia/Kolkata

data_root: ./data/assignments

api:
  youtube_batch_size: 50
  retry_attempts: 4

verification:
  default_duration_change_severity: critical
  default_title_change_severity: warning
  default_description_change_severity: warning
  duration_tolerance_seconds: 2
  baseline_delay_after_deadline: PT15M
```

OAuth credentials/client secrets must be stored outside source control.

---

## 35. Authentication

Implement instructor-side Google OAuth.

The user should authenticate once and reuse a locally stored refresh token securely.

The application should request only the necessary Google Classroom permissions.

Students do not need to authenticate to this application.

The verifier should not request write access to YouTube. It is an observer.

---

## 36. Security Requirements

- HTTPS in any deployed environment.
- No credentials in Git.
- `.gitignore` must exclude token/secret files.
- Never log tokens.
- Dashboard must be instructor-only.
- No public API endpoint for arbitrary video checks unless authenticated.
- Sanitize filenames/assignment identifiers used to construct paths.
- Never allow untrusted URL input to become a filesystem path.

---

## 37. Privacy Requirements

Store only information necessary for the assignment/audit process.

Do not download or archive the video itself.

Store metadata and raw API responses only as needed.

Student/team information should remain within the local course data directory.

---

## 38. Optional Student Metadata Form (Phase 2)

Do not block the MVP on this feature.

A future Google Form or small web form could collect:

- team name
- student names/IDs
- YouTube URL
- video duration
- video title
- upload timestamp
- original filename
- original file size
- original SHA-256
- resolution
- recording time
- teacher-generated challenge code

Treat student-provided values as supporting evidence rather than authoritative evidence.

A teacher-generated challenge code shown in the video is likely more useful than a manually entered hash for establishing provenance.

---

## 39. Optional Browser Hash Tool (Phase 2)

A future student-side browser page may allow a student to select their original MP4 and compute SHA-256 locally in the browser.

The browser would output:

- SHA-256
- filename
- file size
- MIME type
- optionally media duration/resolution

The application would store the student's original-file hash as an unverified provenance claim.

This is not part of MVP.

---

## 40. No Video Download Requirement

The MVP must not use YouTube download/scraping mechanisms to retrieve the student's actual video.

Do not implement yt-dlp or similar tools as part of the core integrity engine.

This keeps the application legally, operationally, and technically simpler and avoids recreating the original storage problem.

---

## 41. Unit Tests

Implement tests for:

### URL parsing

- standard watch URL
- short URL
- URL with timestamp
- URL with `si` parameter
- shorts / embed / live URLs
- Classroom `youTubeVideo.id`
- malformed URL
- non-YouTube URL

### Baseline

- creates correctly
- remains immutable
- duplicate baseline rejected

### Verification

- unchanged video -> GREEN
- title change -> YELLOW
- description change -> YELLOW
- duration change beyond tolerance -> RED
- duration change of 1s with tolerance 2s -> GREEN
- privacy unlisted -> unlisted -> GREEN
- privacy unlisted -> public -> YELLOW
- privacy unlisted -> private -> RED
- channel change -> RED
- video unavailable (empty items after retries) -> RED with `VIDEO_UNAVAILABLE`, not a deletion claim
- video ID changed in Classroom -> RED even if policy says URL is frozen
- incomplete baseline duration filled once when processed -> not `DURATION_CHANGED`
- subsequent duration change after complete baseline -> RED
- API outage -> ERROR, not RED
- repeated identical verification -> new snapshot run; prior runs untouched

### Storage

- correct assignment directory created
- timestamped check directory created
- raw JSON written
- old check not overwritten
- CSV parse/write round trips correctly

---

## 42. Integration Tests

Use mocked Google Classroom and YouTube API responses.

Do not make the test suite depend on live production APIs.

Test a complete run:

```text
Classroom submission
    -> YouTube URL
    -> baseline
    -> later check
    -> detected change
    -> RED result
    -> results.csv
    -> metadata.json
```

Also test API failure recovery.

---

## 43. Acceptance Test: Normal Submission

Given:

- Classroom submission exists;
- YouTube video exists;
- same video ID;
- same channel ID;
- same duration;
- same privacy;
- same material metadata;

When verification runs,

Then:

```text
status = GREEN
```

and a timestamped check directory is created.

---

## 44. Acceptance Test: Duration Modified

Given:

Baseline:

```text
video_id = ABC123
duration = PT4M18S
```

Current:

```text
video_id = ABC123
duration = PT6M31S
```

When verification runs,

Then:

```text
event = DURATION_CHANGED
status = RED
```

and the results CSV contains both durations.

---

## 45. Acceptance Test: Different Video Submitted

Baseline:

```text
ABC123
```

Current Classroom submission:

```text
XYZ789
```

When verification runs,

Then:

```text
event = VIDEO_ID_CHANGED
status = RED
```

The original baseline remains untouched.

---

## 46. Acceptance Test: Deleted Video

Given the baseline video ID is valid, but YouTube subsequently reports the video as not found,

Then after retry handling:

```text
event = VIDEO_UNAVAILABLE
status = RED
```

Do not erase the baseline. Do not claim deletion.

---

## 47. Acceptance Test: Metadata-Only Change

Given:

```text
title baseline = "DS7 Team 17"
title current  = "DS7 Team 17 FINAL"
```

and all material video properties remain unchanged,

Then:

```text
event = TITLE_CHANGED
status = YELLOW
```

Do not classify this as RED by default.

---

## 48. Acceptance Test: API Outage

Given YouTube returns a transient 503,

Then:

- retries occur;
- the check is marked `ERROR` if retries fail;
- no `VIDEO_NOT_FOUND` event is created solely due to the outage;
- other teams continue to be processed;
- the run completes with an error count.

---

## 49. Acceptance Test: Multiple Assignments

Given 15 assignment directories exist,

When the dashboard opens,

Then all 15 assignments can be listed and selected.

Selecting DS07 must only load:

```text
data/assignments/DS07/
```

and must not mix results with DS06 or DS08.

---

## 50. Acceptance Test: Historical Integrity

Given three verification runs:

```text
20260820_094215
20260821_101030
20260825_091544
```

Then all three remain available after the third run.

The dashboard can show the latest run, but the earlier runs remain individually inspectable.

---

## 51. Acceptance Test: Assignment Portability

Copy:

```text
data/assignments/DS07/
```

to another machine.

The application must be able to open and display the stored historical results without requiring a database migration.

---

## 52. Reporting

The application should allow export of a final assignment summary as CSV.

Suggested columns:

```text
team_id
team_name
submitted_at
youtube_url
video_id
baseline_captured_at
last_verified_at
status
events
resolution
penalty_points
resolution_reason
```

Optional HTML summary can be added later.

---

## 53. UI Design Principles

Keep the interface deliberately simple.

The main objective is to answer:

> "Which teams do I need to investigate?"

The first screen should emphasize:

- number of submissions
- number GREEN
- number YELLOW
- number RED
- number ERROR
- last verification time
- baseline capture time
- one `CAPTURE BASELINE` button (disabled once a complete baseline exists, except incomplete-row completion)
- one large `RUN VERIFICATION` button for grading-time snapshots

Avoid complex charts in the MVP.

---

## 54. Important Language in the UI

Use:

- "Integrity issue detected"
- "Change detected since baseline"
- "Video unavailable"
- "Review required"
- "Current artifact differs from baseline"
- "GREEN: no configured change since baseline captured at <time>"

Do NOT use:

- "Cheating detected"
- "Student cheated"
- "Academic misconduct confirmed"
- "Video deleted" when the API only returned empty items
- "Unchanged since submission" when the freeze is the post-deadline baseline

The application is a screening/audit system and must not automatically make disciplinary determinations. Instructor resolutions and optional penalty points are local notes for the gradebook, not proof of misconduct.

---

## 55. Recommended Initial Workflow

### Student instructions (put in the assignment brief and README)

- Upload as **unlisted** (not private, not public). Private videos are invisible to the verifier and to staff.
- Do not open YouTube Studio Editor after the deadline (no trim, cut, blur, or audio replace).
- Do not delete the video or change it to private.
- The Classroom URL is expected to stay frozen; attaching a different video will be flagged.

The app cannot enforce YouTube-side behavior. These rules exist so staff deductions are predictable.

### After deadline (~15 minutes later)

The instructor opens the verifier and presses `CAPTURE BASELINE` once.

### While grading

Staff press `RUN VERIFICATION` whenever they are grading. Each press is a new snapshot. All snapshots remain inspectable.

### Dashboard

```text
GREEN  -> no configured change since baseline (not proof of unaltered pixels/audio)
YELLOW -> inspect if relevant
RED    -> investigate; record a resolution / optional penalty if deducting
ERROR  -> rerun/check API
```

---

## 56. Development Order for Codex

Implement in this order. Do not attempt to build the whole application at once.

### Phase 1: Project skeleton

- Python package
- configuration
- logging
- filesystem utilities
- assignment directory creation
- CSV utilities
- JSON snapshot utilities

### Phase 2: YouTube integration

Before Classroom integration, build a small service that:

- accepts a video URL
- extracts the video ID
- calls YouTube `videos.list`
- returns normalized metadata
- handles missing video/error cases
- writes a sample JSON snapshot

This validates the most important external API behavior first.

### Phase 3: Classroom integration

Implement:

- OAuth
- course listing
- coursework listing
- submission listing
- attachment extraction, preferring `youTubeVideo.id`
- `submissionHistory` / reclaim detection
- submission timestamp extraction
- YouTube URL extraction (watch, short, embed, shorts, live)
- roster.csv mapping

### Phase 4: Baseline engine

Implement:

- baseline schema
- baseline CSV
- immutable baseline handling
- incomplete baseline completion (duration fill-once after `processed`)
- normalized metadata
- metadata hashing
- baseline fingerprint

### Phase 5: Verification engine

Implement all comparison rules and severity classification.

### Phase 6: Timestamped check runs

Implement:

```text
checks/<timestamp>/results.csv
checks/<timestamp>/metadata.json
checks/<timestamp>/raw/*.json
```

No overwrite behavior.

### Phase 7: Dashboard

Implement:

- assignment selection
- assignment summary with deadline, baseline time, last verification time
- team table
- team detail view
- `CAPTURE BASELINE` and `RUN VERIFICATION` buttons
- instructor resolution / optional penalty
- links to YouTube/Classroom

### Phase 8: Testing

Create comprehensive mocked integration tests.

### Phase 9: Documentation

Write `README.md` containing:

- setup
- Google API credential creation
- OAuth configuration
- first run
- adding an assignment
- roster mapping
- student assignment brief (unlisted; no Studio Editor after deadline)
- baseline workflow (`CAPTURE BASELINE` ~15 minutes after deadline)
- verification workflow (repeatable grading-time snapshots)
- what GREEN/YELLOW/RED/ERROR do and do not mean
- blur/audio and pre-baseline coverage limits
- troubleshooting
- backup/archiving

---

## 57. First Implementation Goal

The first useful milestone is NOT the dashboard.

Codex should first produce a command-line prototype that can:

```bash
python scripts/check_youtube.py \
  --url "https://www.youtube.com/watch?v=ABC123"
```

and output something like:

```text
Video ID:        ABC123
Channel ID:      UCxyz
Published:       2026-08-19T17:55:12Z
Duration:        00:04:18
Privacy:         unlisted
Upload status:   processed
Title:           DS7-Team17
ETag:            "abc..."
```

Once this works reliably, integrate it with Classroom.

---

## 58. Suggested Python Package Structure

```text
app/
├── __init__.py
├── main.py
├── auth.py
├── classroom.py
├── youtube.py
├── models.py
├── storage.py
├── verification.py
├── rules.py
├── dashboard.py
├── config.py
└── utils.py

scripts/
├── check_youtube.py
├── discover_classroom.py
└── create_assignment.py

tests/
├── test_url_parser.py
├── test_youtube.py
├── test_classroom.py
├── test_roster.py
├── test_storage.py
├── test_verification.py
├── test_resolutions.py
└── test_integration.py
```

Keep API-specific code isolated from verification logic so that the verifier can be tested without live APIs.

---

## 59. Data/Domain Model

Use Python dataclasses or Pydantic models such as:

```python
class Submission:
    assignment_id: str
    team_id: str
    team_name: str
    classroom_submission_id: str
    submitted_at: datetime
    youtube_url: str
    video_id: str


class VideoSnapshot:
    video_id: str
    channel_id: str
    published_at: datetime | None
    duration: str | None
    privacy_status: str | None
    upload_status: str | None
    title: str | None
    description_hash: str | None
    tags_hash: str | None
    etag: str | None


class VerificationResult:
    status: str
    events: list[str]
    baseline: VideoSnapshot | None
    current: VideoSnapshot | None
```

Do not couple these domain objects directly to raw Google API response schemas.

---

## 60. Normalization Rules

Before comparison:

- canonicalize YouTube URL;
- normalize timestamps to timezone-aware UTC internally where useful;
- normalize description consistently before hashing;
- normalize tags deterministically;
- parse ISO 8601 YouTube duration into seconds for comparisons, while preserving original representation for reporting;
- normalize null/missing values consistently.

Do not compare arbitrary raw JSON serialization because field order or irrelevant changes may create false differences.

---

## 61. Fingerprint Construction

Create a deterministic metadata fingerprint from material baseline fields.

Example canonical object:

```json
{
  "video_id": "ABC123",
  "channel_id": "UCxyz",
  "published_at": "2026-08-19T17:55:12Z",
  "duration_seconds": 258,
  "privacy_status": "unlisted",
  "upload_status": "processed",
  "title": "DS7-Team17",
  "description_hash": "...",
  "tags_hash": "..."
}
```

Serialize using deterministic JSON key ordering and SHA-256 the result.

Store the resulting fingerprint in the baseline.

For a current verification, calculate a current fingerprint too. It is a convenience for audit reporting; the application should still report individual changed fields.

---

## 62. No Database Requirement

Do not introduce SQLite, PostgreSQL, MySQL, MongoDB, or another database in the MVP.

The expected dataset is small:

- approximately 85 teams/students per assignment;
- approximately 15 assignments;
- approximately 1,275 submission records across a semester;
- likely only a handful of verification runs per assignment.

Filesystem + CSV + JSON is sufficient and preferred.

If the project later grows to many courses/instructors or concurrent users, migration to SQLite/PostgreSQL can be considered, but the current architecture should not assume this.

---

## 63. Archiving

An assignment directory must be independently archivable.

Example:

```bash
zip -r DS07_archive.zip data/assignments/DS07/
```

The archive should contain:

- assignment configuration
- roster
- submissions
- baseline
- instructor resolutions
- all verification runs
- all raw snapshots

No database dump should be required.

---

## 64. Git Recommendations

It is acceptable to version the application source in Git.

It is NOT acceptable to commit:

- Google OAuth client secrets
- OAuth refresh tokens
- student-sensitive data if institutional policy prohibits it

The assignment data directory should be configurable so that it can be kept out of the source repository if desired.

Suggested `.gitignore`:

```text
credentials/
*.token.json
.env
__pycache__/
.venv/
```

Whether `data/assignments/` is committed should be an explicit user choice.

---

## 65. Final Product Definition

The finished MVP should feel like a small local application, not an enterprise platform.

The instructor should be able to:

1. Start the application.
2. Authenticate with Google.
3. Select a Classroom assignment and confirm roster/team mapping.
4. See all submissions.
5. About 15 minutes after the deadline, press `CAPTURE BASELINE` once.
6. While grading, press `RUN VERIFICATION` as often as needed. Every run is kept.
7. Immediately see GREEN / YELLOW / RED / ERROR results labeled against the baseline time.
8. Click a red/yellow team to see exactly which observable fields changed.
9. Record a local resolution and optional penalty; export CSV for the gradebook.
10. Open the original YouTube video and Classroom submission.
11. Archive the assignment folder when grading is complete.

The application should optimize for:

- correctness
- auditability
- simplicity
- human-readable files
- low operational burden
- no video storage
- honest claims about what GREEN does and does not prove

rather than for scalability or infrastructure sophistication.

---

## 66. Final Implementation Instruction to Codex

Implement the system incrementally.

First prove the YouTube API integration. Then prove Classroom submission retrieval. Then implement local persistence. Then implement the comparison engine. Only after those components are working should the dashboard be added.

At every stage:

- write tests;
- keep provider/API code separate from domain logic;
- preserve immutable historical records;
- fail safely on API errors;
- never interpret API errors as student misconduct;
- never overwrite a baseline or historical check silently;
- never download/store the student video as part of the core system.

The application must be able to operate entirely from the filesystem and remain useful if the dashboard is unavailable by allowing the instructor to inspect the CSV and JSON files directly.

---

## 67. Fidelity Review Additions (required for MVP)

These are not optional polish. They are part of the MVP.

### 67.1 Official baseline at deadline + 15 minutes

- One class-wide `CAPTURE BASELINE` about 15 minutes after `deadline_at`.
- Later `RUN VERIFICATION` runs compare only to that baseline.
- UI always shows deadline, baseline capture time, and verification time.

### 67.2 Keep URL / ID / reclaim detection

- Still emit `VIDEO_ID_CHANGED` and `CLASSROOM_SUBMISSION_RECLAIMED` even if policy says the Classroom URL cannot change.
- Prefer native `youTubeVideo.id`; still parse watch / short / embed / shorts / live URLs.

### 67.3 Duration tolerance and incomplete baselines

- Compare duration in seconds with default tolerance of 2 seconds.
- Freeze duration only after `uploadStatus=processed`.
- Allow one completion of an incomplete baseline duration; that fill is not tampering.

### 67.4 Multiple grading-time runs

- Every `RUN VERIFICATION` creates a new `checks/<timestamp>/` directory.
- Never overwrite prior runs. Earlier runs stay inspectable.

### 67.5 Instructor resolution and optional penalty

Store `data/assignments/<ASSIGNMENT_ID>/resolutions.csv`:

```text
assignment_id
team_id
decision
penalty_points
reason
decided_at
decided_by
related_check_timestamp
```

`decision` is `none` | `ignore` | `confirmed` | `exception`. Do not write Classroom grades. Include these columns in CSV export.

### 67.6 Roster and native YouTube attachment IDs

- `roster.csv` maps Classroom students to `team_id`.
- Unmapped students: `UNMAPPED_STUDENT`.
- Conflicting videos in a team: `TEAM_MULTIPLE_VIDEOS`; do not guess.

### 67.7 `VIDEO_UNAVAILABLE`

Empty YouTube `items` after retries is `VIDEO_UNAVAILABLE` (RED). Private and deleted are indistinguishable. Do not claim deletion.

### 67.8 Assignment instructions

README and the student brief must say: leave the video unlisted; do not use Studio Editor after the deadline; do not delete or make private.

### 67.9 Honest coverage limits

Document in UI and README:

- GREEN is “no configured observable change since the post-deadline baseline.”
- GREEN is not “unchanged since Turn in.”
- GREEN is not “pixels and audio are unchanged.” Studio blur and audio replacement are not detectable via the Data API.
- Edits already processed before the baseline are out of scope.

