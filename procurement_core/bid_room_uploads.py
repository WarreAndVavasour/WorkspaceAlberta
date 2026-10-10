"""Bring-your-own-documents uploads for the hosted APC bid room.

APC only releases posting documents to a signed-in supplier account, and a
download adds that account to the posting's public Interested Suppliers list.
WorkspaceAlberta therefore never signs in to APC. Each user downloads the
documents with their own APC account and uploads them here:

1. ``process_bid_room`` for an APC reference with no readable public files
   returns a private upload link instead of failing. The link is a signed,
   expiring capability (:func:`create_upload_token`) bound to the reference
   and the caller's tenant.
2. The upload page asks the server for one Supabase Storage signed upload URL
   per file (:func:`signed_upload_url`); the browser sends the bytes straight to
   Storage, so Cloud Run's request-size limit does not apply.
3. ``process_bid_room`` is called again with ``upload_token``.
   :func:`load_uploaded_files` downloads the files, expands an APC "Download
   All" ZIP, verifies type signatures and hashes, and returns the same
   download shape the local harness path uses, so the existing sandbox
   processor runs unchanged.
4. Files are deleted after processing (:func:`delete_session`); unprocessed
   uploads become unreachable when the link expires.

Nothing here stores APC credentials or talks to purchasing.alberta.ca.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import time
import zipfile
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

BUCKET = "bid-room-uploads"
TOKEN_TTL_SECONDS = 2 * 60 * 60
MAX_UPLOAD_FILES = 40
MAX_UPLOAD_BYTES = 100 * 1024 * 1024        # per uploaded file (a "Download All" ZIP can be large)
MAX_SESSION_BYTES = 150 * 1024 * 1024       # everything a session may hold
MAX_ZIP_MEMBERS = 64
UPLOAD_SUFFIXES = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".zip"}
SIGNATURES = {".pdf": b"%PDF-", ".docx": b"PK", ".xlsx": b"PK", ".zip": b"PK"}
_TOKEN_PREFIX = "wabr1"


class UploadError(ValueError):
    """An upload session or file cannot be used. No sandbox was started."""


# ---------------------------------------------------------------------------
# Availability and tokens
# ---------------------------------------------------------------------------


def uploads_available() -> bool:
    """Hosted uploads need Supabase Storage and a tenant to bind the link to."""
    from procurement_core import storage

    return storage._supabase_available() and bool(storage.current_tenant())


def _tenant_digest(tenant: str) -> str:
    return hashlib.sha256(str(tenant).encode("utf-8")).hexdigest()[:24]


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(body: str) -> str:
    from procurement_core.oauth import signing_key

    return _b64(hmac.new(signing_key(), f"{_TOKEN_PREFIX}.{body}".encode("ascii"), hashlib.sha256).digest())


def create_upload_token(reference: str, tenant: str, *, now: float | None = None) -> str:
    claims = {
        "r": reference,
        "t": _tenant_digest(tenant),
        "s": secrets.token_hex(12),
        "e": int((now or time.time()) + TOKEN_TTL_SECONDS),
    }
    body = _b64(json.dumps(claims, separators=(",", ":")).encode("utf-8"))
    return f"{_TOKEN_PREFIX}.{body}.{_sign(body)}"


def verify_upload_token(
    token: str,
    *,
    reference: str | None = None,
    tenant: str | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Return the token claims, or raise :class:`UploadError`."""
    parts = str(token or "").strip().split(".")
    if len(parts) != 3 or parts[0] != _TOKEN_PREFIX:
        raise UploadError("This upload link is not valid.")
    body, signature = parts[1], parts[2]
    if not hmac.compare_digest(_sign(body), signature):
        raise UploadError("This upload link is not valid.")
    try:
        claims = json.loads(_unb64(body))
    except (ValueError, json.JSONDecodeError) as exc:
        raise UploadError("This upload link is not valid.") from exc
    if int(claims.get("e", 0)) < (now or time.time()):
        raise UploadError("This upload link has expired. Ask for a new one by running the bid room again.")
    if not re.fullmatch(r"[0-9a-f]{24}", str(claims.get("s", ""))):
        raise UploadError("This upload link is not valid.")
    if reference is not None and claims.get("r") != reference:
        raise UploadError(f"This upload link is for {claims.get('r')}, not {reference}.")
    if tenant is not None and not hmac.compare_digest(str(claims.get("t", "")), _tenant_digest(tenant)):
        raise UploadError("This upload link belongs to a different account.")
    return claims


def upload_page_url(token: str) -> str:
    from procurement_core.oauth import public_origin

    return f"{public_origin()}/bid-room/upload/{token}"


def session_prefix(claims: dict[str, Any]) -> str:
    return f"{claims['t']}/{claims['s']}"


# ---------------------------------------------------------------------------
# Supabase Storage (REST, service role)
# ---------------------------------------------------------------------------


def _storage_request(method: str, path: str, *, payload: Any = None, raw: bool = False, timeout: int = 30):
    from procurement_core.auth import supabase_config

    url, key = supabase_config()
    if not url or not key:
        raise UploadError("Document uploads are not configured on this server.")
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        f"{url}/storage/v1/{path}",
        data=data,
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method=method,
    )
    with urlopen(request, timeout=timeout) as response:
        body = response.read()
    if raw:
        return body
    return json.loads(body) if body else None


_bucket_ready = False


def ensure_bucket() -> None:
    """Create the private bucket once per process; existing buckets are fine."""
    global _bucket_ready
    if _bucket_ready:
        return
    try:
        _storage_request("POST", "bucket", payload={
            "id": BUCKET, "name": BUCKET, "public": False, "file_size_limit": MAX_UPLOAD_BYTES,
        })
    except HTTPError as exc:
        if exc.code not in (400, 409):  # already exists
            raise
    _bucket_ready = True


def clean_file_name(name: str) -> str:
    base = Path(str(name or "").replace("\\", "/")).name
    base = re.sub(r"[^A-Za-z0-9._ ()-]+", "_", base).strip(" ._")
    return base[:150]


def validate_upload_request(name: str, size: Any, existing: list[dict[str, Any]]) -> str:
    """Check one file before issuing an upload URL. Returns the clean name."""
    clean = clean_file_name(name)
    suffix = Path(clean).suffix.lower()
    if not clean or suffix not in UPLOAD_SUFFIXES:
        raise UploadError(f"{name or 'File'}: only PDF, Word, Excel and ZIP files can be uploaded.")
    try:
        size = int(size)
    except (TypeError, ValueError) as exc:
        raise UploadError(f"{clean}: file size is missing.") from exc
    if size <= 0:
        raise UploadError(f"{clean}: the file is empty.")
    if size > MAX_UPLOAD_BYTES:
        raise UploadError(f"{clean}: larger than the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit.")
    if len(existing) >= MAX_UPLOAD_FILES:
        raise UploadError(f"At most {MAX_UPLOAD_FILES} files can be uploaded for one bid room.")
    if sum(int(item.get("bytes") or 0) for item in existing) + size > MAX_SESSION_BYTES:
        raise UploadError(f"These uploads exceed the {MAX_SESSION_BYTES // (1024 * 1024)} MB total limit.")
    return clean


def signed_upload_url(claims: dict[str, Any], name: str, size: Any) -> dict[str, str]:
    ensure_bucket()
    existing = list_session_files(claims)
    clean = validate_upload_request(name, size, existing)
    object_path = f"{session_prefix(claims)}/{clean}"
    result = _storage_request("POST", f"object/upload/sign/{BUCKET}/{quote(object_path)}", payload={})
    relative = str((result or {}).get("url") or "")
    if not relative.startswith("/object/upload/sign/"):
        raise UploadError("Storage did not return an upload URL.")
    from procurement_core.auth import supabase_config

    base, _key = supabase_config()
    return {"name": clean, "upload_url": f"{base}/storage/v1{relative}"}


def list_session_files(claims: dict[str, Any]) -> list[dict[str, Any]]:
    ensure_bucket()
    rows = _storage_request("POST", f"object/list/{BUCKET}", payload={
        "prefix": f"{session_prefix(claims)}/", "limit": MAX_UPLOAD_FILES + 10,
        "sortBy": {"column": "name", "order": "asc"},
    }) or []
    files = []
    for row in rows:
        if not isinstance(row, dict) or not row.get("name") or row.get("id") is None:
            continue  # folders have no id
        metadata = row.get("metadata") or {}
        files.append({"name": row["name"], "bytes": int(metadata.get("size") or 0)})
    return files


def download_session_file(claims: dict[str, Any], name: str) -> bytes:
    path = f"{session_prefix(claims)}/{clean_file_name(name)}"
    return _storage_request("GET", f"object/authenticated/{BUCKET}/{quote(path)}", raw=True, timeout=60)


def delete_session(claims: dict[str, Any]) -> None:
    """Best-effort removal of every file in the session."""
    try:
        names = [item["name"] for item in list_session_files(claims)]
        if names:
            _storage_request("DELETE", f"object/{BUCKET}", payload={
                "prefixes": [f"{session_prefix(claims)}/{name}" for name in names],
            })
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Turning uploads into the bid room's download shape
# ---------------------------------------------------------------------------


def _normalize_stem(name: str) -> str:
    stem = Path(str(name or "")).stem.lower()
    return re.sub(r"[^a-z0-9]+", "", stem)


def _expand(name: str, data: bytes, out: list[tuple[str, bytes]], warnings: list[str]) -> None:
    """Flatten ZIPs (APC "Download All") one level deep, safely."""
    if Path(name).suffix.lower() != ".zip":
        out.append((name, data))
        return
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        out.append((name, data))  # left for the signature check to reject
        return
    members = [item for item in archive.infolist() if not item.is_dir()]
    if len(members) > MAX_ZIP_MEMBERS:
        warnings.append(f"{name}: only the first {MAX_ZIP_MEMBERS} of {len(members)} files were opened.")
    total = 0
    for member in members[:MAX_ZIP_MEMBERS]:
        member_name = clean_file_name(member.filename)
        if not member_name or member_name.startswith("__MACOSX") or member_name.startswith("._"):
            continue
        if member.file_size > MAX_UPLOAD_BYTES or total + member.file_size > MAX_SESSION_BYTES:
            warnings.append(f"{name}: {member_name} is too large to open.")
            continue
        content = archive.read(member)
        total += len(content)
        out.append((member_name, content))  # nested ZIPs go to the sandbox as-is


def load_uploaded_files(
    claims: dict[str, Any],
    *,
    apc_manifest: list[dict[str, Any]] | None = None,
    max_file_bytes: int | None = None,
) -> dict[str, Any]:
    """Return the ``load_local_download``-shaped dict for uploaded files."""
    from procurement_core.e2b_bid_room import MAX_FILE_BYTES

    limit = MAX_FILE_BYTES if max_file_bytes is None else max_file_bytes
    listed = list_session_files(claims)
    if not listed:
        raise UploadError(
            "No documents have been uploaded yet. Open the upload link, add the files you "
            "downloaded from APC, then run the bid room again with the same upload_token."
        )
    warnings: list[str] = []
    expanded: list[tuple[str, bytes]] = []
    for item in listed:
        _expand(item["name"], download_session_file(claims, item["name"]), expanded, warnings)

    files: list[dict[str, Any]] = []
    seen: set[str] = set()
    for name, data in expanded:
        suffix = Path(name).suffix.lower()
        digest = hashlib.sha256(data).hexdigest()
        record = {
            "title": Path(name).stem or name, "name": name, "path": None, "data": data,
            "sha256": digest, "bytes": len(data), "source": "user_upload",
            "retrieved_at": "", "status": "verified", "error": "",
        }
        signature = SIGNATURES.get(suffix)
        if digest in seen:
            record.update(status="duplicate", error="Same file uploaded twice.")
        elif suffix not in UPLOAD_SUFFIXES:
            record.update(status="unsupported_type", error=f"{suffix or 'No extension'} files are not processed.")
        elif len(data) > limit:
            record.update(status="too_large", error=f"Larger than the {limit} byte bid room limit.")
        elif signature and not data.startswith(signature):
            record.update(status="bad_signature", error=f"Not a valid {suffix} file.")
        seen.add(digest)
        files.append(record)

    complete = None
    expected = None
    if apc_manifest:
        expected = len(apc_manifest)
        uploaded_stems = {_normalize_stem(item["name"]) for item in files if item["status"] == "verified"}
        missing = [
            str(entry.get("name") or "")
            for entry in apc_manifest
            if _normalize_stem(entry.get("name", "")) not in uploaded_stems
        ]
        complete = not missing
        if missing:
            warnings.append(
                "Not uploaded yet (listed on APC): " + ", ".join(missing[:10])
                + (" …" if len(missing) > 10 else "")
            )
    return {
        "reference": claims["r"],
        "folder": None,
        "complete": bool(complete) if complete is not None else True,
        "expected_documents": expected,
        "files": files,
        "warnings": warnings,
    }
