"""HTTP routes for the private APC bid-room upload page.

The page is reached only through the signed, expiring link that
``process_bid_room`` returns (see :mod:`procurement_core.bid_room_uploads`).
Bytes go from the browser straight to Supabase Storage through one signed
upload URL per file; this service never proxies document bodies.
"""

from __future__ import annotations

import asyncio
import re
from html import escape
from typing import Any

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from procurement_core import bid_room_uploads as uploads
from procurement_core.auth_pages import auth_page

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


CONTENT = """
<h1>Upload the tender package.</h1>
<p class="intro">Download the files for <strong>__REF__</strong> from Alberta Purchasing Connection with your own supplier account, then add them here. Your assistant reads them from this private bid room.</p>
<dl class="ledger">
  <div><dt>Reference</dt><dd>__REF__</dd></div>
  <div><dt>Link expires</dt><dd id="expiry">__EXPIRES__</dd></div>
  <div><dt>Limits</dt><dd>__MAX_MB__ MB per file &middot; __SESSION_MB__ MB in total &middot; __MAX_FILES__ files</dd></div>
</dl>
<h2 class="upload-steps-title">Three steps</h2>
<ol class="upload-steps">
  <li>Open <a href="https://purchasing.alberta.ca/posting/__REF__" target="_blank" rel="noopener noreferrer">__REF__ on APC</a> and sign in with <strong>your own supplier account</strong>.</li>
  <li>Under <strong>Document downloads</strong>, choose <strong>Download All</strong>, or download each file including every addendum.</li>
  <li>Drop the files below. The ZIP from <strong>Download All</strong> is fine as it is.</li>
</ol>
<label class="dropzone" id="drop" for="picker">
  <input id="picker" type="file" multiple accept=".pdf,.docx,.doc,.xlsx,.xls,.zip">
  <span class="drop-title">Drop the files here</span>
  <span class="primary-button">Choose files</span>
  <small>PDF, Word, Excel or ZIP</small>
</label>
<ul class="upload-list" id="files" aria-live="polite"><li><span class="empty">Nothing uploaded yet.</span></li></ul>
<p class="upload-total"><span><span id="used">0.0</span> of __SESSION_MB__ MB</span><span class="meter"><i id="meter"></i></span><span><span id="nfiles">0</span> files</span></p>
<section class="expected" aria-labelledby="expected-heading">
  <h2 id="expected-heading">What APC lists</h2>
  __EXPECTED__
</section>
<div class="say">
  <p>When the files show as uploaded, go back to your assistant and say:</p>
  <q id="say">The files for __REF__ are uploaded.</q>
  <button type="button" class="secondary-button" id="copy">Copy</button>
</div>
<p class="subscription-note">Files are kept in private storage in Canada (Supabase, ca-central-1) for this bid room only. The bid-room review deletes them when it finishes; the requirement list keeps them so the review can use the same upload. WorkspaceAlberta never signs in to APC.</p>
"""

SCRIPT = """<script>
(() => {
const base = location.pathname.replace(/\\/$/, "");
const MAX = __MAX_BYTES__, SESSION = __SESSION_BYTES__, MAXFILES = __MAX_FILES__, EXPIRES = __EXPIRES_AT__ * 1000;
const OK = [".pdf", ".docx", ".doc", ".xlsx", ".xls", ".zip"];
const list = document.getElementById("files");
let uploaded = [];
const mb = (b) => (b / 1048576).toFixed(1);
const stem = (n) => String(n).toLowerCase().replace(/\\.[a-z0-9]+$/, "").replace(/[^a-z0-9]+/g, "");
function tick() {
  const left = Math.max(0, Math.floor((EXPIRES - Date.now()) / 60000)), el = document.getElementById("expiry");
  el.className = left < 15 ? "expires-soon" : "";
  el.textContent = left <= 0 ? "Expired. Ask your assistant for a new link." : "in " + (left >= 60 ? Math.floor(left / 60) + " h " + (left % 60) + " min" : left + " min");
}
function row(name) {
  const li = document.createElement("li");
  li.innerHTML = '<span class="nm"></span><span class="st"></span><span class="bar"><i></i></span>';
  li.querySelector(".nm").textContent = name;
  const empty = list.querySelector(".empty"); if (empty) empty.parentElement.remove();
  list.prepend(li); return li;
}
function status(li, text, cls, pct) {
  const st = li.querySelector(".st"); st.textContent = text; st.className = "st" + (cls ? " " + cls : "");
  if (pct != null) li.querySelector(".bar i").style.width = pct + "%";
}
function render() {
  const used = uploaded.reduce((a, f) => a + (f.bytes || 0), 0);
  document.getElementById("used").textContent = mb(used);
  document.getElementById("nfiles").textContent = uploaded.length;
  document.getElementById("meter").style.width = Math.min(100, (100 * used) / SESSION) + "%";
  const names = uploaded.map((f) => stem(f.name)), zip = uploaded.some((f) => /\\.zip$/i.test(f.name));
  const items = document.querySelectorAll(".expected li[data-name]"); let got = 0;
  items.forEach((li) => {
    const s = stem(li.dataset.name), hit = names.some((n) => n && s && (n === s || n.includes(s) || s.includes(n)));
    li.className = hit ? "got" : zip ? "zip" : ""; if (hit) got++;
    li.querySelector(".st").textContent = hit ? "uploaded" : zip ? "check the ZIP" : "not yet";
  });
  const c = document.getElementById("count");
  if (c) c.textContent = got + " of " + items.length + " matched by file name." + (zip ? " Your assistant checks what is inside a ZIP when it reads the files." : "");
}
async function refresh() {
  try {
    const r = await fetch(base + "/files", { cache: "no-store" }); if (!r.ok) return;
    uploaded = (await r.json()).files || [];
    list.replaceChildren();
    if (!uploaded.length) list.innerHTML = '<li><span class="empty">Nothing uploaded yet.</span></li>';
    for (const f of uploaded) status(row(f.name), mb(f.bytes) + " MB \\u00b7 uploaded", "ok", 100);
    render();
  } catch (e) {}
}
function put(url, file, li) {
  return new Promise((resolve, reject) => {
    const x = new XMLHttpRequest(), form = new FormData();
    form.append("cacheControl", "3600"); form.append("", file);
    x.open("PUT", url);
    x.upload.onprogress = (e) => { if (e.lengthComputable) status(li, Math.round((100 * e.loaded) / e.total) + "%", "", (100 * e.loaded) / e.total); };
    x.onload = () => (x.status < 300 || x.status === 409) ? resolve() : reject(new Error(x.status === 413 ? "Too large for storage." : "Storage refused the file (" + x.status + ")."));
    x.onerror = () => reject(new Error("The connection dropped. Add this file again."));
    x.send(form);
  });
}
async function send(file) {
  const li = row(file.name);
  const ext = (file.name.match(/\\.[^.]+$/) || [""])[0].toLowerCase();
  const used = uploaded.reduce((a, f) => a + (f.bytes || 0), 0);
  const err = !OK.includes(ext) ? "Not a PDF, Word, Excel or ZIP file." : file.size > MAX ? "Larger than " + Math.round(MAX / 1048576) + " MB." :
    used + file.size > SESSION ? "Over the " + Math.round(SESSION / 1048576) + " MB total for this bid room." :
    uploaded.length >= MAXFILES ? "This bid room already has " + MAXFILES + " files." : "";
  try {
    if (err) throw new Error(err);
    status(li, "starting", "", 2);
    const s = await fetch(base + "/sign", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: file.name, size: file.size }) });
    const signed = await s.json();
    if (!s.ok) throw new Error(signed.detail || "Upload refused.");
    await put(signed.upload_url, file, li);
    status(li, mb(file.size) + " MB \\u00b7 uploaded", "ok", 100);
    uploaded = uploaded.filter((f) => f.name !== (signed.name || file.name)).concat({ name: signed.name || file.name, bytes: file.size });
    render();
  } catch (e) { status(li, e.message, "bad", 0); }
}
async function handle(files) { for (const f of files) await send(f); }
const drop = document.getElementById("drop"), picker = document.getElementById("picker");
picker.addEventListener("change", (e) => { handle([...e.target.files]); picker.value = ""; });
drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
drop.addEventListener("dragleave", () => drop.classList.remove("over"));
drop.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("over"); handle([...e.dataTransfer.files]); });
document.getElementById("copy").addEventListener("click", (e) => {
  const b = e.currentTarget, t = document.getElementById("say").textContent;
  const fail = () => { b.textContent = "Select the line to copy"; };
  try { navigator.clipboard.writeText(t).then(() => { b.textContent = "Copied"; }, fail); } catch (x) { fail(); }
});
tick(); setInterval(tick, 20000); refresh();
})();
</script>"""


def _fill(template: str, values: dict[str, str]) -> str:
    return re.sub("|".join(map(re.escape, values)), lambda m: values[m.group(0)], template)


def render_page(claims: dict[str, Any], expected: list[str]) -> str:
    import time

    minutes = max(0, int((claims["e"] - time.time()) // 60))
    expires = f"in {minutes // 60} h {minutes % 60} min" if minutes >= 60 else f"in {minutes} min"
    if expected:
        items = "".join(
            f'<li data-name="{escape(name)}"><span class="nm">{escape(name)}</span><span class="st">not yet</span></li>'
            for name in expected
        )
        expected_html = f'<ul>{items}</ul><p class="count" id="count">0 of {len(expected)} matched by file name.</p>'
    else:
        expected_html = ('<p class="none">APC&rsquo;s document list could not be loaded. Upload every file on the '
                         "posting, including each addendum.</p>")
    reference = escape(claims["r"])
    values = {
        "__REF__": reference,
        "__EXPIRES__": escape(expires),
        "__EXPIRES_AT__": str(int(claims["e"])),
        "__EXPECTED__": expected_html,
        "__MAX_MB__": str(uploads.MAX_UPLOAD_BYTES // (1024 * 1024)),
        "__SESSION_MB__": str(uploads.MAX_SESSION_BYTES // (1024 * 1024)),
        "__MAX_BYTES__": str(uploads.MAX_UPLOAD_BYTES),
        "__SESSION_BYTES__": str(uploads.MAX_SESSION_BYTES),
        "__MAX_FILES__": str(uploads.MAX_UPLOAD_FILES),
    }
    return auth_page(
        f"Upload documents for {claims['r']} · workspaceAlberta",
        _fill(CONTENT, values),
        step=claims["r"], step_total="", step_label="Bid room upload",
        product_label="Bid room upload", caption="Private to this bid room.", variant="wide",
        script=_fill(SCRIPT, values),
    )


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
