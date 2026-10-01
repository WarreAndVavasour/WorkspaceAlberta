"""APC file discovery without logging in, downloading or registering suppliers."""

import ipaddress
import socket
from urllib.parse import parse_qsl, quote, urlparse


APC_ACCESS_MESSAGE = (
    "APC document access may require sign-in, supplier registration/notifications "
    "or an NDA. This tool does not perform those actions. Supply an already "
    "authorized public copy with apc_document_urls, or explicitly request "
    "max_attachments=0 for a notice-only review."
)


def apc_posting_url(reference, app_base="https://purchasing.alberta.ca"):
    return f"{app_base.rstrip('/')}/posting/{quote(str(reference), safe='')}"


def public_document_url(value, *, resolve=False):
    """Accept public copies, never APC session/download URLs or URL credentials."""
    parsed = urlparse(str(value or ""))
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https" or not host or parsed.username or parsed.password:
        raise ValueError("Document copies must use public HTTPS URLs without credentials.")
    if host == "purchasing.alberta.ca" or host.endswith(".purchasing.alberta.ca"):
        raise ValueError(APC_ACCESS_MESSAGE)
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        raise ValueError("Document copies must use public HTTPS URLs.")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ValueError("Document copies must use public HTTPS URLs.")
    if parsed.port not in (None, 443):
        raise ValueError("Document copies must use the public HTTPS port.")
    if resolve:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
            raise ValueError("Document copies must resolve to public addresses.")
    if any(key.lower() in {
        "token", "access_token", "api_key", "apikey", "authorization", "cookie",
        "x-amz-signature", "sig", "signature",
    } for key, _value in parse_qsl(parsed.query)):
        raise ValueError("Do not put credentials or authenticated download URLs in tool arguments.")
    return str(value)


def apc_document_manifest(details):
    """Include live procurement files and addenda, excluding deleted versions."""
    opportunity = details.get("opportunity") or details
    rows = {}

    def collect(values, kind):
        if isinstance(values, dict):
            if "documents" in values:
                collect(values["documents"], kind)
                return
            values = [values]
        for item in values or []:
            if not isinstance(item, dict) or item.get("deletedOnUtc"):
                continue
            if "documents" in item:
                collect(item["documents"], kind)
                continue
            document_id = str(item.get("id") or item.get("documentId") or "")
            name = str(item.get("filename") or item.get("title") or "Unnamed APC document")
            key = document_id or name
            entry = {
                "document_id": document_id,
                "name": name,
                "kind": kind,
                "version": item.get("version", 0),
                "amendment_number": item.get("amendmentNumber", 0),
                "expected_bytes": item.get("size"),
                "expected_mime_type": item.get("mimeType") or "",
                "public_url": item.get("downloadUrl") or item.get("url") or "",
                "access_required": bool(
                    opportunity.get("isNdaRequiredForDocumentsAccess")
                    or item.get("requiresAuthentication") or item.get("requiresRegistration")
                ),
            }
            previous = rows.get(key)
            if previous is None or int(entry["version"] or 0) >= int(previous["version"] or 0):
                rows[key] = entry

    for container in (opportunity, details):
        collect(container.get("documents"), "apc_document")
        collect(container.get("addendaDocuments"), "apc_addendum")
    return list(rows.values())


def resolve_apc_documents(details, copies=None, max_attachments=5):
    """Pure metadata resolution. Missing download URLs stay explicitly gated."""
    manifest = apc_document_manifest(details)
    copies = {} if copies is None else copies
    if not isinstance(copies, dict) or len(copies) > 5:
        raise ValueError("apc_document_urls must map at most five APC document IDs to public URLs.")
    known_ids = {item["document_id"] for item in manifest if item["document_id"]}
    if set(copies) - known_ids:
        raise ValueError("apc_document_urls contains an ID not present in this opportunity's documents/addenda.")
    for value in copies.values():
        public_document_url(value)
    limit = max(0, min(5, int(max_attachments)))
    attachments = []
    for item in manifest:
        url = copies.get(item["document_id"]) or item.pop("public_url", "")
        item.pop("public_url", None)
        if limit == 0:
            item.update(status="not_selected", error="Notice-only review explicitly requested.")
        elif item.pop("access_required", False):
            item.update(status="access_required", error=APC_ACCESS_MESSAGE)
        elif not url:
            item.update(status="access_required", error=APC_ACCESS_MESSAGE)
        else:
            try:
                url = public_document_url(url)
            except ValueError as exc:
                item.update(status="access_required", error=str(exc))
                continue
            if len(attachments) >= limit:
                item.update(status="not_selected", error="Attachment limit excludes this document.")
            else:
                item.update(status="selected", url=url, provenance=(
                    "caller_supplied_public_copy" if item["document_id"] in copies else "source_public_url"
                ))
                attachments.append(dict(item))
        item.pop("access_required", None)
    return manifest, attachments
