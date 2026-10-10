"""HTTP routes for the private APC bid-room upload page.

The page is reached only through the signed, expiring link that
``process_bid_room`` returns (see :mod:`procurement_core.bid_room_uploads`).
Bytes go from the browser straight to Supabase Storage through one signed
upload URL per file; this service never proxies document bodies.
"""

from __future__ import annotations

import asyncio
from html import escape
from typing import Any

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from procurement_core import bid_room_uploads as uploads

PRIVATE_HEADERS = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-Robots-Tag": "noindex, nofollow",
}


def _claims(token: str) -> dict[str, Any]:
    try:
        return uploads.verify_upload_token(token)
    except uploads.UploadError as exc:
        raise HTTPException(status_code=404, detail=str(exc), headers=PRIVATE_HEADERS) from exc


def _expected_documents(reference: str) -> list[str]:
    try:
        from procurement_core.apc_documents import apc_document_manifest
        from procurement_core.service import get_alberta_api_details

        return [str(item.get("name") or "") for item in apc_document_manifest(get_alberta_api_details(reference))]
    except Exception:
        return []


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Upload APC documents · WorkspaceAlberta</title>
<style>
:root {{ --bg:#faf8f4; --fg:#1d1d1b; --muted:#5f5b53; --line:#ddd6c8; --accent:#b8860b; --ok:#2f6f3e; --bad:#a3322a; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#141412; --fg:#ece8df; --muted:#a8a294; --line:#3a3731; --accent:#e0b04a; --ok:#7cc48c; --bad:#e8857c; }} }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--fg); font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif; }}
main {{ max-width:680px; margin:0 auto; padding:32px 16px 64px; }}
h1 {{ font-size:1.5rem; margin:0 0 4px; }}
.sub {{ color:var(--muted); margin:0 0 24px; }}
ol {{ padding-left:1.2em; }}
.drop {{ border:2px dashed var(--line); border-radius:12px; padding:28px 16px; text-align:center; margin:20px 0; cursor:pointer; }}
.drop.over {{ border-color:var(--accent); }}
.drop input {{ display:none; }}
ul.files {{ list-style:none; padding:0; margin:0; }}
ul.files li {{ display:flex; justify-content:space-between; gap:12px; padding:8px 0; border-bottom:1px solid var(--line); overflow-wrap:anywhere; }}
.ok {{ color:var(--ok); }} .bad {{ color:var(--bad); }} .muted {{ color:var(--muted); }}
.note {{ font-size:.9rem; color:var(--muted); margin-top:28px; }}
</style></head><body><main>
<h1>Upload documents for {reference}</h1>
<p class="sub">WorkspaceAlberta bid room · private link · expires {expires}</p>
<ol>
<li>Open <a href="https://purchasing.alberta.ca/posting/{reference}" target="_blank" rel="noopener noreferrer">the posting on APC</a> with your own supplier account.</li>
<li>Under <strong>Document downloads</strong>, choose <strong>Download All</strong>, or download each file including every addendum.</li>
<li>Drop the files below, then go back to your assistant and say the files are uploaded.</li>
</ol>
{expected}
<label class="drop" id="drop">
<input id="picker" type="file" multiple accept=".pdf,.docx,.doc,.xlsx,.xls,.zip">
<strong>Choose files</strong> or drop them here<br><span class="muted">PDF, Word, Excel or ZIP · up to 100 MB each</span>
</label>
<h2 style="font-size:1.1rem">Uploaded</h2>
<ul class="files" id="files"><li class="muted">Nothing uploaded yet.</li></ul>
<p class="note">Files are stored privately for this bid room only and deleted after processing. WorkspaceAlberta never signs in to APC.</p>
</main>
<script>
const base = location.pathname.replace(/\\/$/, "");
const list = document.getElementById("files");
function row(name, status, cls) {{
  const li = document.createElement("li");
  const a = document.createElement("span"); a.textContent = name;
  const b = document.createElement("span"); b.textContent = status; if (cls) b.className = cls;
  li.append(a, b); return li;
}}
async function refresh() {{
  try {{
    const r = await fetch(base + "/files", {{cache: "no-store"}});
    const data = await r.json();
    list.replaceChildren();
    if (!data.files || !data.files.length) {{ list.append(row("Nothing uploaded yet.", "", "muted")); return; }}
    for (const f of data.files) list.append(row(f.name, (f.bytes / 1048576).toFixed(1) + " MB ✓", "ok"));
  }} catch (e) {{}}
}}
async function send(file) {{
  const li = row(file.name, "uploading…", "muted"); list.prepend(li);
  try {{
    const s = await fetch(base + "/sign", {{method: "POST", headers: {{"Content-Type": "application/json"}},
      body: JSON.stringify({{name: file.name, size: file.size}})}});
    const signed = await s.json();
    if (!s.ok) throw new Error(signed.detail || "Upload refused");
    const form = new FormData(); form.append("cacheControl", "3600"); form.append("", file);
    const put = await fetch(signed.upload_url, {{method: "PUT", body: form}});
    if (!put.ok && put.status !== 409) throw new Error("Storage rejected the file (" + put.status + ")");
  }} catch (e) {{ li.lastChild.textContent = e.message; li.lastChild.className = "bad"; return; }}
  li.remove();
}}
async function handle(files) {{ for (const f of files) await send(f); refresh(); }}
const drop = document.getElementById("drop");
document.getElementById("picker").addEventListener("change", e => handle(e.target.files));
drop.addEventListener("dragover", e => {{ e.preventDefault(); drop.classList.add("over"); }});
drop.addEventListener("dragleave", () => drop.classList.remove("over"));
drop.addEventListener("drop", e => {{ e.preventDefault(); drop.classList.remove("over"); handle(e.dataTransfer.files); }});
refresh();
</script></body></html>"""


def render_page(claims: dict[str, Any], expected: list[str]) -> str:
    import time

    minutes = max(0, int((claims["e"] - time.time()) // 60))
    expires = f"in {minutes // 60} h {minutes % 60} min" if minutes >= 60 else f"in {minutes} min"
    expected_html = ""
    if expected:
        items = "".join(f"<li>{escape(name)}</li>" for name in expected)
        expected_html = f"<p><strong>APC lists {len(expected)} document(s):</strong></p><ul>{items}</ul>"
    return PAGE.format(reference=escape(claims["r"]), expires=escape(expires), expected=expected_html)


def register_bid_room_upload_routes(app: FastAPI) -> None:
    @app.get("/bid-room/upload/{token}", include_in_schema=False)
    async def upload_page(token: str) -> HTMLResponse:
        claims = _claims(token)
        expected = await asyncio.to_thread(_expected_documents, claims["r"])
        return HTMLResponse(render_page(claims, expected), headers=PRIVATE_HEADERS)

    @app.get("/bid-room/upload/{token}/files", include_in_schema=False)
    async def upload_files(token: str) -> JSONResponse:
        claims = _claims(token)
        try:
            files = await asyncio.to_thread(uploads.list_session_files, claims)
        except uploads.UploadError as exc:
            raise HTTPException(status_code=503, detail=str(exc), headers=PRIVATE_HEADERS) from exc
        return JSONResponse({"reference": claims["r"], "files": files}, headers=PRIVATE_HEADERS)

    @app.post("/bid-room/upload/{token}/sign", include_in_schema=False)
    async def upload_sign(token: str, body: dict[str, Any] | None = Body(default=None)) -> JSONResponse:
        claims = _claims(token)
        body = body or {}
        try:
            signed = await asyncio.to_thread(uploads.signed_upload_url, claims, body.get("name"), body.get("size"))
        except uploads.UploadError as exc:
            raise HTTPException(status_code=400, detail=str(exc), headers=PRIVATE_HEADERS) from exc
        return JSONResponse(signed, headers=PRIVATE_HEADERS)
