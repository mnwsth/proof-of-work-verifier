# Google API credentials (first run)

This app talks to two Google services:

- **Google Classroom** (instructor OAuth) to list courses, assignments, and submissions
- **YouTube Data API v3** (API key) to read observable metadata for submitted video IDs

Students never sign in. The app never writes Classroom grades and never requests YouTube write access.

You need a Google account that is a **teacher** on the Classroom course you will verify.

---

## 1. Create a Google Cloud project

1. Open [Google Cloud Console](https://console.cloud.google.com/).
2. In the project picker (top bar), choose **New project**.
3. Name it something like `proof-of-work-verifier`.
4. Create it, then make sure that project is selected.

---

## 2. Enable the two APIs

In that project:

1. Open [API Library](https://console.cloud.google.com/apis/library).
2. Enable **Google Classroom API**.
3. Enable **YouTube Data API v3**.

Direct links (after the project is selected):

- [Enable Classroom API](https://console.cloud.google.com/apis/library/classroom.googleapis.com)
- [Enable YouTube Data API v3](https://console.cloud.google.com/apis/library/youtube.googleapis.com)

---

## 3. Configure the OAuth consent screen

1. Open [Google Auth Platform](https://console.cloud.google.com/auth/overview) (or **APIs & Services → OAuth consent screen**).
2. If asked for user type:
   - **Internal** if this is a school Google Workspace and only accounts in that domain should sign in.
   - **External** for a personal Gmail project. Keep it in **Testing**.
3. App name: `Proof-of-Work Verifier` (any local name is fine).
4. User support email and developer contact: your instructor address.
5. Scopes: **Add or remove scopes**, filter to **Google Classroom API**, and add these. Search by the human-readable name if the URI is not shown:

```text
https://www.googleapis.com/auth/classroom.courses.readonly
https://www.googleapis.com/auth/classroom.coursework.me.readonly
https://www.googleapis.com/auth/classroom.coursework.students.readonly
https://www.googleapis.com/auth/classroom.rosters.readonly
https://www.googleapis.com/auth/classroom.profile.emails
https://www.googleapis.com/auth/classroom.student-submissions.students.readonly
```

The last one appears as **View course work and grades for students in the Google Classroom classes you teach or administer**. It is enough to read student submissions.

To list assignment titles and due dates (the class picker on the home page), also add a coursework scope. If the picker does not show the `.readonly` URIs, add the closest match:

- **View your course work and grades in Google Classroom** (`classroom.coursework.me.readonly`)
- **See, create, and edit coursework items including assignments, questions, and grades** (`classroom.coursework.students`) if the students readonly scope is missing

The app only reads Classroom data. It never creates coursework or writes grades. After adding a new scope, use **Re-authorize Classroom** on the dashboard so Google shows the consent screen again.

6. If the app is **External** and still in **Testing**, add yourself under **Test users**. Only listed accounts can sign in until the app is published (you do not need to publish it for local use).

YouTube is accessed with an API key, so do **not** add YouTube OAuth scopes.

---

## 4. Create a Desktop OAuth client

1. Open [Credentials](https://console.cloud.google.com/apis/credentials).
2. **Create credentials → OAuth client ID**.
3. Application type: **Desktop app**.
4. Name: `verifier-local`.
5. Create, then **Download JSON**.
6. Save the file as:

```text
credentials/client_secrets.json
```

The download is usually named `client_secret_….json`. Rename it. The file should look like:

```json
{
  "installed": {
    "client_id": "….apps.googleusercontent.com",
    "project_id": "proof-of-work-verifier",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "client_secret": "…",
    "redirect_uris": ["http://localhost"]
  }
}
```

Desktop is required. A Web application client will not work with the local browser sign-in this app uses.

---

## 5. Create a YouTube API key

1. Still on [Credentials](https://console.cloud.google.com/apis/credentials).
2. **Create credentials → API key**.
3. Copy the key.
4. Edit the key:
   - Restrict APIs to **YouTube Data API v3**.
   - Optionally restrict by IP if this machine has a stable address. Skip IP restriction if you are unsure.
5. Save the key as a single line, no quotes, in:

```text
credentials/youtube_api_key.txt
```

---

## 6. Confirm the files on disk

From the project root:

```text
credentials/
├── client_secrets.json      # OAuth Desktop client (you create this)
├── youtube_api_key.txt      # YouTube API key (you create this)
└── token.json               # created automatically after first sign-in
```

Paths are set in `config.yaml` (`oauth.client_secrets_file`, `oauth.youtube_api_key_file`, `oauth.token_file`). Do not commit these files. `.gitignore` already excludes `credentials/`.

---

## 7. First sign-in

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app
```

1. Open http://127.0.0.1:8000
2. Click **Sign in with Google**.
3. A browser window opens. Choose the **instructor** Google account that teaches the course.
4. Google may show **Google hasn’t verified this app**. Choose **Advanced → Go to Proof-of-Work Verifier (unsafe)**. That is expected for a private local project.
5. Grant the Classroom read permissions.
6. The app stores a refresh token at `credentials/token.json`. Later runs reuse it; you should not need to sign in every time.

You can also sign in from the CLI before starting the dashboard:

```bash
python scripts/discover_classroom.py
```

That lists courses if OAuth worked. Then:

```bash
python scripts/check_youtube.py --url "https://www.youtube.com/watch?v=VIDEO_ID"
```

That confirms the YouTube API key can read metadata (use an unlisted or public video you can open in a browser).

---

## What each credential is for

| File | Used for |
|---|---|
| `client_secrets.json` | Starts instructor OAuth |
| `token.json` | Reuses Classroom access after the first sign-in |
| `youtube_api_key.txt` | `videos.list` by video ID (unlisted works if you have the ID; private does not) |

---

## Troubleshooting

**Missing OAuth client secrets**  
`credentials/client_secrets.json` is absent or not the Desktop download. The JSON root key must be `installed`, not `web`.

**Access blocked / app is in testing**  
External apps in Testing only allow **Test users**. Add the instructor account, wait a minute, try again.

**This app isn’t verified**  
Normal. Use Advanced and continue. Do not publish the OAuth app unless you intend to.

**Classroom 403 / no courses**  
You signed in with an account that is not a teacher on the course, or the Classroom API is not enabled on this Cloud project.

**Classroom 403 when opening a class (assignments do not list)**  
Listing titles and due dates needs a coursework scope. Add it on the consent screen, then click **Re-authorize Classroom** so Google prompts again. `student-submissions.students.readonly` alone is not enough for `courseWork.list`.

**YouTube empty / video unavailable**  
Private videos are invisible to an API key. The student video must be **unlisted** (or public). Also confirm YouTube Data API v3 is enabled and the key is in `youtube_api_key.txt` with no extra spaces.

**OAuth works once, then the app shows Internal Server Error**  
Google granted fewer scopes than requested. Restart the app and open `/login` again. If `credentials/token.json` exists from the failed attempt, you can leave it; a valid token will be reused. If you just added a coursework scope, use **Re-authorize Classroom** (`/login?force=1`) so Google can grant it.

**Quota exceeded**  
YouTube `videos.list` is cheap (batched), but a shared demo project can still run out. Check [Quotas](https://console.cloud.google.com/apis/api/youtube.googleapis.com/quotas) for the YouTube Data API.

---

## Security

- Treat `client_secrets.json`, `youtube_api_key.txt`, and `token.json` as secrets.
- Do not log or screenshot the client secret or refresh token.
- The dashboard is meant for one instructor on a local machine.
