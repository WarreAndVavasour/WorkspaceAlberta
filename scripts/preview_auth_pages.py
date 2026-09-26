"""Local-only design preview with fictional identity; never issues OAuth grants.

Run: python scripts/preview_auth_pages.py
Consent: http://127.0.0.1:8765/   Sign-in: http://127.0.0.1:8765/signin
"""
from pathlib import Path
import os
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["CANADABUYS_LOAD_ENV_FILE"] = "0"

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import uvicorn
from procurement_core.auth_pages import auth_page
from procurement_core.oauth_http import _consent_form, _google_form
from procurement_core.public_pages import register_public_pages

app = FastAPI()
register_public_pages(app)


@app.middleware("http")
async def preview_headers(request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.get("/", response_class=HTMLResponse)
async def consent():
    return _consent_form({"authorize_params": {"client_name": "Example AI client",
                           "redirect_uri": "https://client.example/callback"},
                          "user": {"email": "you@example.com"}, "consent_id": "local-preview-only"})


@app.get("/signin", response_class=HTMLResponse)
async def signin():
    return _google_form({"redirect_uri": "https://client.example/callback"})


@app.post("/authorize/consent", response_class=HTMLResponse)
async def preview_decision(request: Request):
    decision = (await request.form()).get("decision")
    heading = "Access allowed" if decision == "approve" else "Connection cancelled"
    return auth_page("Design preview", f'<h1>{heading}</h1><p class="intro">This is a local design preview. No account was connected and no token was issued.</p><p><a href="/">Back to consent preview</a></p>', step="02", step_label="Preview only")


@app.post("/authorize/google", response_class=HTMLResponse)
async def preview_signin():
    return await consent()


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8765)
