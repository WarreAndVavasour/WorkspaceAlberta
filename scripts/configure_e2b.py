#!/usr/bin/env python3
"""Securely configure a local E2B key for WorkspaceAlberta.

The key is read with getpass (no terminal echo), never accepted as a command-line
argument, and stored only in the repo-local gitignored .env with mode 0600.
"""

from __future__ import annotations

import getpass
import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT_DIR / ".env"


def validate_e2b_key(value: str) -> str:
    key = value.strip()
    if not key.startswith("e2b_") or len(key) <= len("e2b_"):
        raise ValueError("Expected an E2B API key beginning with 'e2b_'.")
    if "\n" in key or "\r" in key:
        raise ValueError("The E2B API key must be a single line.")
    return key


def update_env_text(original: str, key: str) -> str:
    replacement = f"E2B_API_KEY={validate_e2b_key(key)}"
    lines = original.splitlines()
    output: list[str] = []
    replaced = False
    for line in lines:
        if line.strip().startswith("E2B_API_KEY="):
            if not replaced:
                output.append(replacement)
                replaced = True
            continue
        output.append(line)
    if not replaced:
        output.append(replacement)
    return "\n".join(output) + "\n"


def write_secret_env(path: Path, key: str) -> None:
    original = path.read_text(encoding="utf-8") if path.exists() else ""
    updated = update_env_text(original, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(updated)
    finally:
        os.chmod(path, 0o600)


def next_steps() -> str:
    return (
        "Next steps:\n"
        "  uv venv .venv  # only if .venv does not already exist\n"
        "  uv pip install --python .venv/bin/python -r requirements.txt\n"
        "  .venv/bin/python scripts/e2b_bid_room_smoke.py"
    )


def main() -> int:
    print("WorkspaceAlberta E2B setup")
    print("The key is hidden while you type and is not sent through chat.")
    print(f"It will be stored in the gitignored file {ENV_PATH} with mode 0600.")
    first = getpass.getpass("E2B API key: ")
    second = getpass.getpass("Confirm E2B API key: ")
    if first != second:
        print("Keys did not match; nothing was written.")
        return 1
    try:
        key = validate_e2b_key(first)
    except ValueError as error:
        print(f"Invalid key: {error}")
        return 1
    write_secret_env(ENV_PATH, key)
    print("E2B key saved securely.")
    print(next_steps())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
