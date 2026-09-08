"""Read/write allowlisted Google Sheets only."""

from __future__ import annotations

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

from app.config import AppConfig


class SheetAccessError(RuntimeError):
    pass


def assert_allowed(config: AppConfig, spreadsheet_id: str) -> None:
    allowed = config.oauth.allowed_spreadsheet_ids
    if spreadsheet_id not in allowed:
        raise SheetAccessError(
            f"Spreadsheet {spreadsheet_id} is not in oauth.allowed_spreadsheet_ids"
        )


def sheets_service(creds: Credentials):
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def get_spreadsheet(config: AppConfig, creds: Credentials, spreadsheet_id: str) -> dict:
    assert_allowed(config, spreadsheet_id)
    return sheets_service(creds).spreadsheets().get(spreadsheetId=spreadsheet_id).execute()


def get_values(
    config: AppConfig,
    creds: Credentials,
    spreadsheet_id: str,
    range_name: str,
) -> list[list]:
    assert_allowed(config, spreadsheet_id)
    result = (
        sheets_service(creds)
        .spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=range_name)
        .execute()
    )
    return result.get("values") or []


def update_values(
    config: AppConfig,
    creds: Credentials,
    spreadsheet_id: str,
    range_name: str,
    values: list[list],
) -> dict:
    assert_allowed(config, spreadsheet_id)
    return (
        sheets_service(creds)
        .spreadsheets()
        .values()
        .update(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption="USER_ENTERED",
            body={"values": values},
        )
        .execute()
    )
