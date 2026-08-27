"""Cohere Parse helpers shared by host tests and the E2B bid-room processor.

Official API (https://docs.cohere.com/reference/parse):

- POST https://api.cohere.com/v2/parse
- model: parse-v5.0
- document.type is image_url only (data URI or remote http(s) image URL)
- PDF / file URL / DOCX / XLSX document objects are not accepted

Bid-room PDFs are rasterized to JPEG pages in the sandbox, then each page is
sent as image_url. Images go to Parse directly. DOCX/XLSX stay on the
deterministic extractors. Parse failures fall back to those extractors.
"""

import base64
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PARSE_MODEL_DEFAULT = "parse-v5.0"
PARSE_URL = "https://api.cohere.com/v2/parse"
PARSE_MAX_IMAGE_BYTES = 20 * 1024 * 1024
PARSE_DEFAULT_TIMEOUT = 60
PARSE_DEFAULT_MAX_PAGES = 16
EXTRACT_FALLBACK = "fallback"
EXTRACT_INLINE = "inline"
PARSE_USER_AGENT = "WorkspaceAlberta-BidRoom/0.1"
PARSE_CLIENT_NAME = "WorkspaceAlberta-BidRoom"

IMAGE_MIME_BY_SUFFIX = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
}


def parse_kind(name, content_type=""):
    """Return ``image``, ``pdf``, or ``""`` for types the Parse API cannot take."""
    suffix = str(name or "").rsplit(".", 1)
    ext = f".{suffix[-1].lower()}" if len(suffix) == 2 else ""
    ctype = str(content_type or "").split(";", 1)[0].strip().lower()
    if ext in IMAGE_MIME_BY_SUFFIX or ctype.startswith("image/"):
        return "image"
    if ext == ".pdf" or "pdf" in ctype:
        return "pdf"
    return ""


def image_mime(name, content_type=""):
    """Return an image MIME type for a Parse data URI."""
    suffix = str(name or "").rsplit(".", 1)
    ext = f".{suffix[-1].lower()}" if len(suffix) == 2 else ""
    if ext in IMAGE_MIME_BY_SUFFIX:
        return IMAGE_MIME_BY_SUFFIX[ext]
    ctype = str(content_type or "").split(";", 1)[0].strip().lower()
    if ctype.startswith("image/"):
        return ctype
    return "image/png"


def data_uri(data, mime):
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def build_parse_request(data, mime, model=PARSE_MODEL_DEFAULT):
    """Build the official Parse body. Do not invent file/pdf document types."""
    return {
        "model": model,
        "document": {
            "type": "image_url",
            "image_url": data_uri(data, mime),
        },
        "output_format": "markdown",
    }


def markdown_from_parse_response(result):
    """Join page markdown from a Parse response."""
    if not isinstance(result, dict):
        return ""
    pages = result.get("pages") or []
    parts = []
    for page in pages:
        if not isinstance(page, dict):
            continue
        markdown = page.get("markdown")
        if isinstance(markdown, dict):
            content = markdown.get("content") or ""
        elif isinstance(markdown, str):
            content = markdown
        else:
            content = ""
        if str(content).strip():
            parts.append(str(content).strip())
    return "\n\n".join(parts)


def call_cohere_parse(
    data,
    mime,
    api_key,
    model=PARSE_MODEL_DEFAULT,
    endpoint=PARSE_URL,
    timeout=PARSE_DEFAULT_TIMEOUT,
    opener=None,
):
    """POST one image to Cohere Parse. Raises RuntimeError on HTTP/timeout errors."""
    if not api_key:
        raise RuntimeError("parse_unset")
    if not data:
        raise RuntimeError("parse_empty_image")
    if len(data) > PARSE_MAX_IMAGE_BYTES:
        raise RuntimeError("parse_too_large")
    request = Request(
        endpoint,
        data=json.dumps(build_parse_request(data, mime, model)).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": PARSE_USER_AGENT,
            "X-Client-Name": PARSE_CLIENT_NAME,
        },
        method="POST",
    )
    opener = opener or urlopen
    try:
        with opener(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        raise RuntimeError(f"parse_http_{exc.code}: {body[:300]}") from exc
    except TimeoutError as exc:
        raise RuntimeError("parse_timeout") from exc
    except URLError as exc:
        reason = str(getattr(exc, "reason", exc))
        if "timed out" in reason.lower():
            raise RuntimeError("parse_timeout") from exc
        raise RuntimeError(f"parse_url_error: {reason}") from exc


def run_parse_or_fallback(
    kind,
    parse_enabled,
    api_key,
    parse_fn,
    fallback_fn,
    model=PARSE_MODEL_DEFAULT,
):
    """Prefer Parse for image/pdf kinds; keep the deterministic extractor on failure.

    Returns ``(text, extract_method, parse_error)``.
    ``extract_method`` is the Parse model id on success, otherwise ``fallback``.
    """
    if not kind:
        return fallback_fn(), EXTRACT_FALLBACK, "unsupported_mime"
    if not parse_enabled:
        return fallback_fn(), EXTRACT_FALLBACK, "parse_disabled"
    if not str(api_key or "").strip():
        return fallback_fn(), EXTRACT_FALLBACK, "parse_unset"
    try:
        text = parse_fn()
    except Exception as exc:
        return fallback_fn(), EXTRACT_FALLBACK, str(exc)[:400]
    if not str(text or "").strip():
        return fallback_fn(), EXTRACT_FALLBACK, "parse_empty"
    return text, model, ""


def summarize_extract_methods(documents, model=PARSE_MODEL_DEFAULT):
    """Estimator-facing summary of which files used Parse vs fallback."""
    parsed = []
    fallback = []
    for item in documents or []:
        name = str(item.get("name") or "")
        method = str(item.get("extract_method") or "")
        if method == model:
            parsed.append(name)
        elif method == EXTRACT_FALLBACK:
            fallback.append(name)
    return {
        "model": model,
        "files_used_parse": parsed,
        "files_used_fallback": fallback,
    }
