# Google API credentials (first run)

This repo talks to Google as **your instructor account**. Students never sign in here.

| Service | What for |
|---|---|
| **Google Classroom** | List courses and submissions (verifier). Create **draft** POW assignments (create scripts). |
| **Google Forms** | Create the YouTube submission Form attached to each POW. |
| **Google Sheets** | Optional: read/write allowlisted planning/rubric spreadsheets. |
| **YouTube Data API v3** | Read observable metadata for submitted video IDs (API key, not OAuth). |

The verifier never writes Classroom grades and never requests YouTube write access.

You need a Google account that is a **teacher** on the Classroom course you will use.

---

## 1. Create a Google Cloud project

1. Open [Google Cloud Console](https://console.cloud.google.com/).
2. **New project**, name it something like `proof-of-work-verifier`.
3. Select that project.

Use **your** Cloud project. Do not reuse another instructor’s OAuth client or API key.

---

## 2. Enable APIs

In that project, enable:

- [Google Classroom API](https://console.cloud.google.com/apis/library/classroom.googleapis.com)
- [YouTube Data API v3](https://console.cloud.google.com/apis/library/youtube.googleapis.com)
- [Google Forms API](https://console.cloud.google.com/apis/library/forms.googleapis.com) (needed to create POW Forms)
- [Google Sheets API](https://console.cloud.google.com/apis/library/sheets.googleapis.com) (needed if you use a rubric spreadsheet)

---

## 3. Configure the OAuth consent screen

1. Open [Google Auth Platform](https://console.cloud.google.com/auth/overview) (or **APIs & Services → OAuth consent screen**).
2. User type: **Internal** for school Workspace (only that domain can sign in), or **External** + **Testing** for a personal Gmail project.
3. App name: `Proof-of-Work Verifier` (any local name is fine).
4. User support email and developer contact: your instructor address.
5. Add scopes. The **dashboard verifier** needs Classroom read + (if you use Sheets) spreadsheets:

```text
https://www.googleapis.com/auth/classroom.courses.readonly
https://www.googleapis.com/auth/classroom.coursework.me.readonly
https://www.googleapis.com/auth/classroom.coursework.students.readonly
https://www.googleapis.com/auth/classroom.rosters.readonly
https://www.googleapis.com/auth/classroom.profile.emails
https://www.googleapis.com/auth/classroom.student-submissions.students.readonly
https://www.googleapis.com/auth/spreadsheets
```

`student-submissions.students.readonly` appears as **View course work and grades for students in the Google Classroom classes you teach or administer**.

To list assignment titles on the home page you also need a coursework scope (`classroom.coursework.me.readonly` or `classroom.coursework.students`).

**Create-script** runs also request write scopes (Forms body, Classroom coursework create, Drive file for Form creation). Google will prompt when a script first runs. After adding scopes, use **Re-authorize Classroom** (`/login?force=1`) or delete `credentials/token.json` so consent runs again.

6. If the app is **External** and in **Testing**, add yourself under **Test users**.

Do **not** add YouTube OAuth scopes. YouTube uses an API key.

---

## 4. Create a Desktop OAuth client

1. [Credentials](https://console.cloud.google.com/apis/credentials) → **Create credentials → OAuth client ID**.
2. Application type: **Desktop app**.
3. Download JSON and save as:

```text
credentials/client_secrets.json
```

The JSON root key must be `installed`, not `web`. A Web client will not work with the local browser callback.

---

## 5. Create a YouTube API key

1. **Create credentials → API key**.
2. Restrict the key to **YouTube Data API v3**.
3. Save as a single line, no quotes:

```text
credentials/youtube_api_key.txt
```

---

## 6. Local course config

```bash
cp config.local.yaml.example config.local.yaml
```

Fill in **your** IDs (never commit this file):

- `google.classroom_course_id` — from Classroom or `python scripts/discover_classroom.py`
- `oauth.allowed_spreadsheet_ids` — spreadsheet IDs this machine may read/write (empty list if you do not use Sheets)
- `google.admin_folder_id` / `reflections_folder_id` / `reflections_topic_id` — only if you use those Drive/Classroom extras

Committed `config.yaml` must not contain course, Drive, or spreadsheet IDs.

---

## 7. Files on disk

```text
credentials/
├── client_secrets.json      # OAuth Desktop client
├── youtube_api_key.txt      # YouTube API key
└── token.json               # created after first sign-in
config.local.yaml            # your course and spreadsheet IDs
```

`.gitignore` excludes `credentials/` and `config.local.yaml`.

---

## 8. First sign-in

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app
```

1. Open http://127.0.0.1:8000 → **Sign in with Google**.
2. Choose the **instructor** account that teaches **your** course.
3. **Google hasn’t verified this app** is expected: **Advanced → continue**.
4. Grant Classroom (and Sheets, if requested) permissions.

CLI check:

```bash
python scripts/discover_classroom.py
python scripts/check_youtube.py --url "https://www.youtube.com/watch?v=VIDEO_ID"
```

Creating a POW Form/assignment the first time may open another consent window for Forms and Classroom write access. See [Creating POW assignments](creating-pow-assignments.md).

---

## What each credential is for

| File | Used for |
|---|---|
| `client_secrets.json` | Starts instructor OAuth |
| `token.json` | Reuses Google access after the first sign-in |
| `youtube_api_key.txt` | `videos.list` by video ID (unlisted works if you have the ID; private does not) |
| `config.local.yaml` | Your course / Drive / spreadsheet IDs |

---

## Troubleshooting

**Missing OAuth client secrets**  
`credentials/client_secrets.json` is absent or not a Desktop download (`installed`).

**Access blocked / app is in testing**  
External apps in Testing only allow **Test users**.

**This app isn’t verified**  
Normal. Use Advanced and continue. You do not need to publish the OAuth app for local use.

**Classroom 403 / no courses**  
Wrong Google account, or Classroom API not enabled on this Cloud project.

**Classroom 403 when opening a class**  
Need a coursework list scope. Re-authorize after adding it.

**Forms or Sheets 403 API not used**  
Enable Forms or Sheets on the same project, wait a minute, retry.

**Request had insufficient authentication scopes**  
The stored token is missing a scope (often `spreadsheets` or Forms). Delete `credentials/token.json` or force re-consent.

**YouTube empty / video unavailable**  
Private videos are invisible to an API key. Students must submit **unlisted** (or public).

**Quota exceeded**  
[YouTube Data API quotas](https://console.cloud.google.com/apis/api/youtube.googleapis.com/quotas).

---

## Security

- Treat `client_secrets.json`, `youtube_api_key.txt`, `token.json`, and `config.local.yaml` as secrets.
- Do not log or screenshot the client secret or refresh token.
- Do not commit another institution’s course IDs or student data.
- The dashboard is meant for one instructor on a local machine.
