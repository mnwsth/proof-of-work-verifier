# YouTube Proof-of-Work Integrity Verifier

Instructor tools for a hardware course that collects **unlisted YouTube proof-of-work videos** through Google Forms (linked from Google Classroom), then checks whether those videos still look the same after the deadline.

This repository is meant to be reused by another instructor offering the same kind of course. You bring your own Classroom class, Google Cloud project, and student domain. Nothing in git should contain your OAuth secrets, API keys, or course/Drive IDs.

Two jobs:

1. **Create** draft Classroom assignments and Google Forms for each POW (see [Creating POW assignments](docs/creating-pow-assignments.md)).
2. **Verify** submitted YouTube URLs against a class-wide baseline (this README).

The verifier is a screening tool. It does not download videos, does not hash YouTube bytes, and does not decide academic misconduct.

## What GREEN / YELLOW / RED / ERROR mean

- **GREEN**: no configured observable change since the post-deadline baseline. Not “unchanged since Turn in.” Not “pixels and audio are unchanged.”
- **YELLOW**: a configured change that usually needs a look (title, description, unlisted → public).
- **RED**: a material integrity issue to review (duration beyond tolerance, different video ID, video unavailable, channel change, unlisted → private).
- **ERROR**: API/network/quota failure. Never treat this as a student integrity finding.

YouTube Studio **blur** and **audio replacement** keep the same video ID and duration. The Data API cannot see those edits. Edits that finished processing **before** the official baseline become the baseline.

## Setup

Python 3.12+ recommended.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.local.yaml.example config.local.yaml
```

Edit `config.local.yaml` with **your** Classroom course ID, Drive folder IDs (if you use them), and any spreadsheet IDs this machine may read or write. That file is gitignored. Committed `config.yaml` only has timezone, verifier defaults, and paths to credential files.

Set `timezone` in `config.yaml` to the zone you use for due dates (default `Asia/Kolkata`).

### Google API credentials (once)

Follow **[docs/google-api-credentials.md](docs/google-api-credentials.md)**. In short:

1. Create a Google Cloud project. Enable **Classroom**, **YouTube Data API v3**, **Google Forms**, and **Google Sheets**.
2. Configure the OAuth consent screen (add yourself as a test user if the app is External).
3. Create an OAuth client of type **Desktop app** → `credentials/client_secrets.json`.
4. Create a YouTube API key → `credentials/youtube_api_key.txt` (one line, no quotes).
5. Do not commit `credentials/` or `config.local.yaml`.

Students never sign in. The verifier does not write Classroom grades and does not request YouTube write access. Creating POW Forms/assignments needs extra OAuth scopes; the first create script will open a consent window.

### First run (verifier dashboard)

```bash
python -m app
```

Open http://127.0.0.1:8000 and click **Sign in with Google** as a **teacher** on the course. A refresh token is stored at `credentials/token.json`.

```bash
python scripts/discover_classroom.py
python scripts/check_youtube.py --url "https://www.youtube.com/watch?v=VIDEO_ID"
```

## Creating POW assignments

POW submissions go through a **Google Form** (team lead only, Unlisted YouTube URL + 11-character video ID). Classroom holds a **draft** assignment with the Form attached until you publish it.

See **[docs/creating-pow-assignments.md](docs/creating-pow-assignments.md)** for the full workflow: shared student instructions, copying a create script, assignee lists, Form UI toggles, and rubric spreadsheets.

Student-facing rules to hand out (also in `STUDENT_BRIEF.md`): Unlisted YouTube, at least 30 seconds, no Studio edits after the deadline, late policy applies to the **whole team**.

## Add an assignment to the verifier

Sign in, then click a class on the home page. Import a published Classroom assignment whose due date is still in the future, or:

```bash
python scripts/create_assignment.py \
  --assignment-id DS07 \
  --name "Digital Systems - Proof of Work 7" \
  --course-id COURSE_ID \
  --coursework-id COURSEWORK_ID \
  --deadline "2026-08-20T23:59:00+05:30" \
  --draft-roster
```

Then edit `data/assignments/DS07/roster.csv` and fill `team_id` / `team_name`. Unmapped students are `UNMAPPED_STUDENT`. If teammates attach different videos, the team is `TEAM_MULTIPLE_VIDEOS`.

## Baseline workflow

1. Team leads submit YouTube URLs in the Form (Classroom should point at that Form).
2. Prefer closing the Form after the due date (this freezes new responses, not the YouTube video).
3. About **15 minutes after the deadline**, press **Capture baseline** once.
4. Videos still processing are `baseline_incomplete`. Capture again only to fill duration. That fill is not treated as tampering.
5. A complete baseline is immutable.

## Verification workflow

Press **Run verification** while grading. Each press writes `data/assignments/<ID>/checks/<YYYYMMDD_HHMMSS>/` (`results.csv`, `metadata.json`, raw YouTube JSON). Older runs are never overwritten.

Record a local resolution (`ignore` / `confirmed` / `exception`) and optional penalty. Export CSV for the gradebook. This app does not write Classroom grades.

## Coverage limits

Detectable with high confidence after the baseline: trim/cut (duration beyond 2 seconds), video unavailable, privacy unlisted → public or private, title/description/tags, a different video ID, submission reclaimed.

Not detectable: Studio blur, Studio audio replacement, cards/end screens/captions/thumbnails, anything that finished processing before the official baseline.

## Troubleshooting

- **ERROR instead of RED**: quota, 5xx, or network. Rerun. Do not deduct points from ERROR.
- **Video unavailable**: private, deleted, or not yet visible. Do not call this “deleted” with certainty.
- **OAuth errors**: delete `credentials/token.json` and sign in again. Never paste tokens into logs or chat. See [Google API credentials](docs/google-api-credentials.md#troubleshooting).

Logs: `logs/verifier.log` (no access or refresh tokens).

## Backup / archiving

```bash
zip -r DS07_archive.zip data/assignments/DS07/
```

Keep `data/assignments/` out of git if it contains student information. Set `data_root` in `config.yaml` to store files elsewhere.

## Tests

```bash
pytest
```

The suite uses mocked Classroom and YouTube responses and does not call live Google APIs.
