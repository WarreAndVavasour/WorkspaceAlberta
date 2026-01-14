#!/usr/bin/env python3
"""
Test Google Drive Connection.
Verifies that OAuth is set up correctly by listing recent files.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

TOKEN_PATH = Path(__file__).resolve().parent.parent / ".credentials" / "google-token.json"
SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.metadata.readonly",
]

COLORS = {
    "reset": "\x1b[0m",
    "green": "\x1b[32m",
    "yellow": "\x1b[33m",
    "red": "\x1b[31m",
    "cyan": "\x1b[36m",
    "dim": "\x1b[2m",
}


def _color(text: str, color: str) -> str:
    return f"{COLORS[color]}{text}{COLORS['reset']}"


def _get_file_type(mime_type: str) -> str:
    types = {
        "application/vnd.google-apps.document": "Google Doc",
        "application/vnd.google-apps.spreadsheet": "Google Sheet",
        "application/vnd.google-apps.presentation": "Google Slides",
        "application/vnd.google-apps.folder": "Folder",
        "application/pdf": "PDF",
        "image/": "Image",
        "video/": "Video",
        "audio/": "Audio",
    }

    for key, value in types.items():
        if mime_type.startswith(key):
            return value
        if key.endswith("/") and mime_type.startswith(key):
            return value
        if key in mime_type:
            return value
    return "File"


def test_connection() -> None:
    print("\nTesting Google Drive connection...\n")

    if not TOKEN_PATH.exists():
        print(_color("[ERROR] No authorization token found.", "red"))
        print('Run "python scripts/oauth_setup.py" first to authorize Google Drive access.\n')
        raise SystemExit(1)

    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")

    if not client_id or not client_secret:
        print(_color("[ERROR] Missing GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET", "red"))
        raise SystemExit(1)

    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    drive = build("drive", "v3", credentials=creds)

    try:
        response = (
            drive.files()
            .list(
                pageSize=10,
                fields="files(id, name, mimeType, modifiedTime)",
                orderBy="modifiedTime desc",
            )
            .execute()
        )
        files = response.get("files", [])

        print(_color("[SUCCESS] Connected to Google Drive!", "green") + "\n")
        print(_color("Your 10 most recent files:", "cyan") + "\n")

        if not files:
            print("  (No files found)")
        else:
            for index, file in enumerate(files, start=1):
                file_type = _get_file_type(file.get("mimeType", ""))
                modified = file.get("modifiedTime")
                date = datetime.fromisoformat(modified.replace("Z", "+00:00")).date() if modified else "Unknown"
                print(f"  {index}. {file.get('name', 'Untitled')}")
                print(
                    f"     {_color(f'Type: {file_type} | Modified: {date}', 'dim')}"
                )

        print(
            "\n"
            + _color("Google Drive is ready to use with your AI assistant!", "green")
        )
        print('Open the AI chat (Ctrl+Shift+I) and try asking about your files.\n')
    except HttpError as exc:
        print(_color(f"[ERROR] Failed to connect: {exc}", "red"))
        if "invalid_grant" in str(exc):
            print("\nYour authorization has expired. Run \"python scripts/oauth_setup.py\" to re-authorize.\n")
        raise SystemExit(1)


if __name__ == "__main__":
    test_connection()
