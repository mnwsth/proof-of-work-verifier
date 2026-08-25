# YouTube Proof-of-Work Integrity Verifier

Instructor-side local app that compares YouTube proof-of-work videos against a class-wide baseline taken about 15 minutes after the assignment deadline. Later grading-time snapshots tell you whether configured, observable properties of the submitted YouTube video ID have changed since that baseline.

This is a screening tool. It does not download videos, does not hash YouTube bytes, and does not determine academic misconduct.

## What GREEN / YELLOW / RED / ERROR mean

- **GREEN**: no configured observable change since the post-deadline baseline. Not “unchanged since Turn in.” Not “pixels and audio are unchanged.”
- **YELLOW**: a configured change that usually needs a look (title, description, unlisted → public).
- **RED**: a material integrity issue to review (duration beyond tolerance, different video ID, video unavailable, channel change, unlisted → private).
- **ERROR**: API/network/quota failure. Never treat this as a student integrity finding.

YouTube Studio **blur** and **audio replacement** keep the same video ID and duration. The Data API cannot see those edits.

Edits that were already processed **before** the official baseline become the baseline. Later checks will not flag them.

## Setup

Python 3.12+ recommended.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Google API credentials (first run)

Follow **[docs/google-api-credentials.md](docs/google-api-credentials.md)** once. In short:

1. Create a Google Cloud project and enable **Google Classroom API** and **YouTube Data API v3**.
2. Configure the OAuth consent screen (add yourself as a test user if the app is External).
3. Create an OAuth client of type **Desktop app** and save it as `credentials/client_secrets.json`.
4. Create a YouTube API key and save it as `credentials/youtube_api_key.txt` (one line, no quotes).
5. Do not commit those files. `.gitignore` already excludes `credentials/`.

OAuth is instructor-only (courses, coursework, submissions, rosters, profile emails). Students never sign in. YouTube is observed with the API key; the app does not request YouTube write access.

### First run

```bash
python -m app
```

Open http://127.0.0.1:8000 and click **Sign in with Google**. Use the instructor account that teaches the course. A refresh token is stored at `credentials/token.json`.

You can also use:

```bash
uvicorn app.main:app --reload
```

### Check a single YouTube URL

```bash
python scripts/check_youtube.py --url "https://www.youtube.com/watch?v=VIDEO_ID"
```

This prints observable metadata only. It does not download the video.

### Discover Classroom IDs

```bash
python scripts/discover_classroom.py
python scripts/discover_classroom.py --course-id COURSE_ID
```

### Add an assignment

Sign in, then click a class on the home page. The app lists published Classroom assignments whose due date is still in the future. Import one to create the local folder and a draft roster. You can still add one by ID at `/assignments/new`, or:

```bash
python scripts/create_assignment.py \
  --assignment-id DS07 \
  --name "Digital Systems - Proof of Work 7" \
  --course-id COURSE_ID \
  --coursework-id COURSEWORK_ID \
  --deadline "2026-08-20T23:59:00+05:30" \
  --draft-roster
```

Then edit `data/assignments/DS07/roster.csv` and fill `team_id` / `team_name` for every student. Unmapped students are flagged `UNMAPPED_STUDENT`. If teammates attach different videos, the team is flagged `TEAM_MULTIPLE_VIDEOS` and no canonical video is guessed.

## Student assignment brief

Give students these rules with the assignment (a copy is in `STUDENT_BRIEF.md`):

- Upload as **unlisted** (not private, not public). Private videos are invisible to staff and to this verifier.
- Do not open YouTube Studio Editor after the deadline (no trim, cut, blur, or audio replace).
- Do not delete the video or change it to private.
- The Classroom URL is expected to stay frozen; attaching a different video will be flagged.

The app cannot enforce YouTube-side behavior.

## Baseline workflow

1. Students submit YouTube URLs in Classroom.
2. Prefer closing Classroom submissions after the due date (this freezes the URL, not the YouTube video).
3. About **15 minutes after the deadline**, press **Capture baseline** once.
4. Videos still processing are stored as `baseline_incomplete`. Press Capture baseline again only to fill those duration fields once. That fill is not treated as tampering.
5. A complete baseline is immutable. The app will not silently overwrite it.

## Verification workflow

While grading, press **Run verification** as often as you like. Each press writes a new `data/assignments/<ID>/checks/<YYYYMMDD_HHMMSS>/` folder with `results.csv`, `metadata.json`, and raw YouTube JSON. Older runs are never overwritten.

On a team page you can record a local resolution (`ignore` / `confirmed` / `exception`) and optional penalty points. Export CSV for the gradebook. This app does not write Google Classroom grades.

## Coverage limits

Detectable with high confidence after the baseline:

- Trim/cut (duration change beyond 2 seconds)
- Video unavailable (private and deleted look the same)
- Privacy unlisted → public or private
- Title / description / tags
- Classroom attachment pointing at a different video ID
- Submission reclaimed / unsubmitted

Not detectable:

- Studio blur
- Studio audio replacement
- Cards, end screens, captions, thumbnails as content edits
- Anything that finished processing before the official baseline

## Troubleshooting

- **ERROR instead of RED**: quota, 5xx, or network. Rerun. Do not deduct points from ERROR.
- **Video unavailable**: the API returned no items. The video may be private, deleted, or not yet visible. Do not call this “deleted” with certainty.
- **Capture baseline disabled**: a complete baseline already exists.
- **Run verification disabled**: capture a baseline first.
- **OAuth errors**: delete `credentials/token.json` and sign in again. Never paste tokens into logs or chat. See [Google API credentials](docs/google-api-credentials.md#troubleshooting).

Logs: `logs/verifier.log` (no access or refresh tokens).

## Backup / archiving

Each assignment folder is self-contained:

```bash
zip -r DS07_archive.zip data/assignments/DS07/
```

That archive has configuration, roster, submissions, baseline, resolutions, every verification run, and raw snapshots. No database dump is required.

Keep `data/assignments/` out of git if it contains student information. Configure `data_root` in `config.yaml` if you want the files stored elsewhere.

## Tests

```bash
pytest
```

The suite uses mocked Classroom and YouTube responses and does not call live Google APIs.
