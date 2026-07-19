# Fresh-Clone UX Report — WorkspaceAlberta

**Test date:** 2026-07-18
**Persona:** brand-new user on Windows (Git Bash), non-developer small-business owner, following only what the repo tells them
**Method:** cloned `https://github.com/HarleyCoops/WorkspaceAlberta.git` into `.tmp/fresh-clone` and followed the documented path literally. No silent workarounds. The existing working copy was not modified.

---

## Verdict

**The wiring works; the welcome mat doesn't.** Every technical step that exists in the docs passed on the first try — clone, install, smoke test, live MCP handshake, first real opportunity search. But the repo never actually *tells* a new user what those steps are: the README is 100% narrative with zero setup instructions, and the only install/run sequence lives in a doc written for AI coding agents (`docs/codex-setup.md`). A developer would muddle through in ~15 minutes. The small-business owner the README is written for would not get there unaided.

---

## Step-by-step log

### 1. Clone

| | |
|---|---|
| Command | `git clone https://github.com/HarleyCoops/WorkspaceAlberta.git .tmp/fresh-clone` |
| Result | ✅ success, exit 0 |
| Time | **5.4 s** |
| Size | **63 MB** total — 39 MB is `.git` history, ~24 MB working tree |

Friction notes: 39 MB of git history is heavy for a repo that describes itself as "intentionally narrow" (likely the `docs/assets/` archival photos and quarantine/output dirs). Not a blocker, but noticeable on rural Alberta bandwidth.

### 2. Read the docs and find the setup path

| | |
|---|---|
| `README.md` (root) | ⚠️ 220 lines of brand narrative, market sizing, and philosophy. **No "Getting Started", no install command, no run command.** Closest thing is a "Technical Notes" link list at the bottom. |
| `mcp-servers/canadabuys/README.md` | ⚠️ Says "Run Directly: `python mcp-servers/canadabuys/server.py`" — but **never mentions installing dependencies first**. On a fresh machine that command dies with `ModuleNotFoundError: No module named 'mcp'`. |
| `docs/codex-setup.md` | ✅ The **only** file with the real sequence (`pip install -r requirements.txt`, then the smoke test). But it's framed as "Codex / OpenClaw Setup" — written for AI agents, three links deep, and a non-developer would never open it. |
| `AGENTS.md` | ⚠️ Agent-facing; references `/home/chris/.local/bin/gbrain` — a path that only exists on the maintainer's Linux machine. |

Friction notes: the user's actual journey is README → confusion → lucky guess at `docs/codex-setup.md`. I logged this as the single biggest failure of the first-run experience.

### 3. Install dependencies

| | |
|---|---|
| Command | `python -m pip install -r requirements.txt` (from fresh clone root) |
| Result | ✅ success, exit 0 — 38 packages installed (mcp 1.28.1, fastapi 0.139.2, uvicorn 0.51.0, e2b 2.34.0, etc.) |
| Time | **49 s** |

Friction notes:
- No doc tells you to do this before `mcp-servers/canadabuys/README.md` says to run the server (see step 2).
- No venv guidance anywhere — the docs have users pip-install into whatever Python is active. Works, but it's how beginners break their base environment.
- **Two** requirements files exist: root (4 deps) and `mcp-servers/canadabuys/requirements.txt` (6 deps, adds `starlette`, `sse-starlette`). Neither doc explains which to use or why there are two. The root one happened to be sufficient for every test.
- `mcp-servers/canadabuys/pyproject.toml` still has placeholder URLs (`https://github.com/your-org/canadabuys-mcp`).

### 4. Smoke tests

| Command | Result | Time |
|---|---|---|
| `python -m unittest tests.test_canadabuys_mcp_smoke` | ✅ **PASS** (1 test: server starts, 21 tools listed, 2 tool calls) | 5.0 s |
| `python -m unittest tests.test_procurement_http_app` | ✅ **PASS** (1 test) | 1.7 s |
| `python -m unittest discover -s tests` (what a curious user runs) | ✅ **PASS — 7 tests, OK** (E2B tests skip cleanly without a key) | 1.3 s |

Friction notes: the HTTP test emits a `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead` — cosmetic, but it's noise a first-timer will read as "something is wrong."

### 5. Start the MCP server and speak MCP to it

| | |
|---|---|
| Command | piped raw JSON-RPC (`initialize` → `notifications/initialized` → `tools/list` → `tools/call get_my_profile`) into `python mcp-servers/canadabuys/server.py` under a 20 s timeout |
| Result | ✅ Server started with no import errors, answered `initialize` (`serverInfo: canadabuys v1.28.1`) and `tools/list` with **21 tools**. The `tools/call` over a bare pipe raced stdin-close, but the smoke test (proper client session) already proved tool calls work. No process left running. |

Friction notes: none for the server itself. (For a non-developer the entire concept of "now wire this stdio server into a client" is the cliff — see step 6.)

### 6. Client configuration path

| File | Finding |
|---|---|
| `mcp.json.example` | ⚠️ Offers 3 options but never says which one a new user should pick. The **hosted HTTP entry actually works today** (verified: `GET /health` → 200, `POST /mcp` initialize → valid handshake) — this zero-install path is the best option for a non-developer and the README never mentions it. The Claude Desktop option silently requires Node.js/`npx` (`mcp-remote`) — not stated. The local stdio option uses a **relative path** and bare `python` — breaks in any client not launched from the repo root, and there's no Windows guidance. |
| `.cursor/mcp.json` | ⚠️ Defines **two** entries for the same product: hosted `workspacealberta` **and** local `buildcanada`. Which one am I supposed to use? `${workspaceFolder}` is Cursor-only. |
| Naming | ⚠️ The same server is called **WorkspaceAlberta**, **canadabuys** (serverInfo name), and **Build Canada / buildcanada** (AGENTS.md, Cursor config) in different files. |
| Machine-specific references | ❌ `AGENTS.md` → `/home/chris/.local/bin/gbrain` (maintainer's Linux box). `docs/setup-productization-track.md` → `C:\Users\chris\wvsetup` and a **private** GitHub repo link that 404s for everyone else. `pyproject.toml` → `your-org` placeholders. |

### 7. Missing env vars, API keys, and network behavior

| Scenario | Behavior | Grade |
|---|---|---|
| No env vars at all | Server starts, all local tools work. Server README's "No environment variables are required for local use" is **true**. | ✅ |
| First live search (`search_opportunities "steel"`) | Returned 3 real opportunities in **~2.2 s**, with an honest warning: *"CanadaBuys cache was empty, so it was refreshed from open data."* Requires open internet to canadabuys.canada.ca + purchasing.alberta.ca. | ✅ excellent |
| `check_cohere_status` with no keys | Clear status page, lists all four accepted env vars, explicitly notes it doesn't call the model or leak tokens. | ✅ exemplary |
| `analyze_contract_with_cohere` with no keys | Graceful: *"Cohere analysis is not available: Hugging Face token is not configured. Set HF_TOKEN or HUGGINGFACEHUB_API_TOKEN."* | ✅ |
| `process_bid_room` with no `E2B_API_KEY` | Graceful: *"Bid room processing is not available: E2B_API_KEY is not configured."* | ✅ |
| `analyze_contract_with_cohere` on an **Alberta** reference returned by unified search | ❌ *"Contract not found: AB-2026-05127"* — analysis only sees federal contracts, but unified search happily hands users Alberta references. Real dead end with a confusing message. | ❌ |
| Default cache dir | `~/.canadabuys` — outside the repo; fine for real users, undocumented side effect. (This test redirected it via `CANADABUYS_DATA_DIR`.) | ℹ️ |

### 8. Housekeeping check — `.tmp` in the main repo

- `C:\Users\chris\WorkspaceAlberta\.gitignore` exists and does **NOT** ignore `.tmp/`. `git check-ignore .tmp` → not ignored; `git status` shows `?? .tmp/`. This report's clone (63 MB with a nested `.git`) currently pollutes the main repo's status. **Recommendation: add `.tmp/` to `.gitignore`** (not done here — out of scope for this test).
- Related discovery: the checked-out working copy has **25 modified/untracked paths vs origin** (~451 insertions across 8 tracked files, plus untracked `docs/mcp-tool-reference.md`, `procurement_core/auth.py`, `pipelines/migrations/`, etc.). **The public repo a fresh user clones is meaningfully older than the code the owner runs** — fresh-clone users are testing yesterday's product.

---

## Time-to-first-value estimate

| Path | Time | Confidence |
|---|---|---|
| **Developer** who guesses `docs/codex-setup.md` exists: clone (5 s) → find setup doc (**5–15 min of hunting** — the only unguided step) → pip install (49 s) → smoke test (5 s) → first live search (2 s) | **~10–20 min** | Verified end-to-end in this test |
| **Non-developer small-business owner** following the README | **Never unaided.** No step in the README is actionable. | — |
| **Fastest real path that exists today** (add hosted URL `https://workspacealberta-719334491060.northamerica-northeast1.run.app/mcp` to any HTTP-native MCP client — verified alive during this test) | **~2 min** | But documented only inside `mcp.json.example`, which a non-developer will never open |

---

## Friction list, ranked by severity (as a small-business user would say it)

1. **"I read the entire front page and I still don't know what to do."** — README has zero setup steps; not even a link labeled "Start here." *(Severity: fatal for the stated audience.)*
2. **"It told me to run the server, and it instantly crashed with `No module named 'mcp'`."** — server README skips the install step entirely. *(Severity: fatal for anyone who finds the server README first.)*
3. **"Is it called WorkspaceAlberta, CanadaBuys, or Build Canada? My config file has two of them and I don't know which to click."** — three names, two overlapping Cursor entries. *(Severity: high confusion, support-ticket generator.)*
4. **"The instructions reference files and folders that don't exist on my computer"** — `/home/chris/.local/bin/gbrain`, `C:\Users\chris\wvsetup`, a private GitHub repo, `your-org` placeholder URLs. *(Severity: trust-eroding; makes the repo feel like someone's personal machine leaked.)*
5. **"Search gave me a reference number, and when I asked for analysis it said the contract doesn't exist."** — Alberta references invisible to `analyze_contract_with_cohere`. *(Severity: broken promise of the flagship "unified" feature.)*
6. **"Which of these three config blocks do I copy, and what is npx?"** — `mcp.json.example` has no guidance, no Windows notes, hidden Node.js prerequisite, relative paths. *(Severity: blocks the final inch.)*
7. **"Which requirements file? And what's a venv?"** — two requirements.txt, no environment guidance. *(Severity: medium; worked by luck on this machine.)*
8. **"A warning about `httpx2` flashed by during the tests — did something fail?"** — cosmetic deprecation noise. *(Severity: low.)*
9. *(Meta)* `.tmp/` isn't gitignored in the main repo, and the published repo lags the owner's working copy by ~25 changed paths. *(Severity: maintainer hygiene.)*

---

## What worked smoothly (honestly and specifically)

- **Every documented technical step that exists passed first try**: clone (5.4 s), pip install (49 s, zero build errors on Windows), both smoke tests, full test discovery (7/7).
- **The server is genuinely zero-config for local use** — no env vars, no keys, starts clean and advertises 21 tools over stdio immediately.
- **First real search returned live Alberta + federal opportunities in ~2 seconds**, including a candid "cache was empty, so it was refreshed" warning — exactly the kind of honest feedback that builds trust.
- **Failure modes for every paid/optional layer (Cohere, Hugging Face, E2B) are graceful and actionable**, with exact env var names in the message. `check_cohere_status` is a model of good DX.
- **The hosted endpoint is alive and answering MCP handshakes today** — a true zero-install path exists; it's just undocumented in the README.
- **E2B-dependent tests skip cleanly** without credentials instead of failing.

---

## Top 5 fixes for first-run experience

1. **Add a "Get started in 5 minutes" section to the top of README.md** with two tracks: *"No install: add this URL to your MCP client"* (the hosted endpoint — it works) and *"Run it yourself: clone → `python -m pip install -r requirements.txt` → `python -m unittest tests.test_canadabuys_mcp_smoke` → copy the `local_stdio` block from `mcp.json.example`."*
2. **Fix `mcp-servers/canadabuys/README.md` to list the install step before "Run Directly"**, and pick one requirements file (or state plainly that root is for local dev, server-dir is for deployment).
3. **One product, one name.** Rename the `buildcanada` client entry to `workspacealberta-local`, say in one sentence why the server package is called `canadabuys`, and stop introducing "Build Canada" in AGENTS.md.
4. **Scrub maintainer-machine artifacts from public docs**: remove/qualify `/home/chris/.local/bin/gbrain`, the private `wvsetup` repo references, and the `your-org` pyproject URLs. Add `.tmp/` to `.gitignore`.
5. **Close the Alberta-reference gap**: either let `analyze_contract_with_cohere` resolve Alberta APC references, or change the error to *"Analysis is only available for federal (CanadaBuys) postings right now — Alberta references like this one aren't supported yet."*

---

*Test environment: Windows, Git Bash, Python 3.12.13, git 2.54.0. Fresh clone retained at `.tmp/fresh-clone` for reference; it is untracked-but-not-ignored in the main repo until `.gitignore` is updated.*
