"""Instructor Google OAuth. Classroom read, YouTube observe-only."""

from __future__ import annotations

import logging
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from app.config import AppConfig

LOGGER = logging.getLogger("verifier")

# Local HTTP is required for the Desktop OAuth callback.
os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")
# Google may omit a requested scope from the granted set; do not treat that as failure.
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

SCOPES = [
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.coursework.me.readonly",
    "https://www.googleapis.com/auth/classroom.coursework.students.readonly",
    "https://www.googleapis.com/auth/classroom.student-submissions.students.readonly",
    "https://www.googleapis.com/auth/classroom.rosters.readonly",
    "https://www.googleapis.com/auth/classroom.profile.emails",
]


class AuthError(RuntimeError):
    pass


def load_api_key(config: AppConfig) -> str | None:
    path = config.resolve(config.oauth.youtube_api_key_file)
    if path.exists():
        key = path.read_text(encoding="utf-8").strip()
        return key or None
    return None


def load_credentials(config: AppConfig) -> Credentials | None:
    token_path = config.resolve(config.oauth.token_file)
    if not token_path.exists():
        return None
    try:
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            save_credentials(config, creds)
            LOGGER.info("Refreshed Google OAuth token")
        return creds
    except Exception:
        LOGGER.exception("Could not load stored Google token")
        return None


def save_credentials(config: AppConfig, creds: Credentials) -> None:
    token_path = config.resolve(config.oauth.token_file)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")


def login(config: AppConfig, force: bool = False) -> Credentials:
    creds = load_credentials(config)
    if creds and creds.valid and not force:
        return creds
    secrets = config.resolve(config.oauth.client_secrets_file)
    if not secrets.exists():
        raise AuthError(f"Missing OAuth client secrets at {secrets}")
    flow = InstalledAppFlow.from_client_secrets_file(str(secrets), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")
    save_credentials(config, creds)
    LOGGER.info("Stored instructor Google OAuth refresh token locally")
    return creds


def is_authenticated(config: AppConfig) -> bool:
    creds = load_credentials(config)
    return bool(creds and creds.valid)
