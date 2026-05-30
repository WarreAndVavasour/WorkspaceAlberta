# Setup and Productization Track

This is the single operating track for turning WorkspaceAlberta into a repeatable product while keeping private corporate setup work in `wvsetup`.

## Source Boundaries

WorkspaceAlberta is the product repo. It owns:

- the CanadaBuys and Alberta Purchasing Connection procurement MCP server
- the shared procurement core
- hosted MCP/REST adapters
- the Hermes / Raspberry Pi appliance installer
- deployment operations notes
- customer-facing product and brand copy
- smoke tests that prove the procurement wiring still starts

`wvsetup` is the private corporate setup repo. It owns:

- Warre & Vavasour account setup profiles
- GitHub, Google Workspace, Hugging Face, model provider, cloud, and observability checklists
- personal-to-company repository migration planning
- human-in-the-loop setup agents
- local inventory notes derived from private environment state

Do not copy private `wvsetup` inventory into this repo. Link the track, summarize the dependency, and keep secrets out of both Git histories.

## Current Connection

The local checkout at `C:\Users\chris\wvsetup` is connected to the private GitHub repo:

```text
https://github.com/HarleyCoops/wvsetup
```

It tracks `origin/main`. The remote repo is private and is expected to move under the future Warre & Vavasour GitHub organization after that org exists.

## One Track

1. Corporate identity first: use `wvsetup/todo.md` and the Tier 0 agents to create or verify GitHub org, Google Workspace, and Hugging Face org.
2. Product repo baseline: keep WorkspaceAlberta focused on procurement MCP, Hermes/Pi packaging, deployment operations, and product copy.
3. Procurement endpoint: keep `mcp-servers/canadabuys/server_http.py` deployable as the hosted MCP/REST product surface.
4. Appliance setup: keep `installer/install-workspace-alberta-pi.sh` and `docs/workspace-alberta-hermes-install.md` as the repeatable customer-terminal setup path.
5. Operations: use `docs/deployment-ops/` for remote support, licensing notes, and leased terminal procedures.
6. Launch readiness: only promote to customer-facing production after credentials, billing, support access, smoke tests, and procurement source behavior are verified.

## Checklist

- [x] Connect local `wvsetup` checkout to the private GitHub repo.
- [x] Put local `wvsetup` on `main` tracking `origin/main`.
- [ ] Create or confirm the Warre & Vavasour GitHub organization.
- [ ] Transfer or recreate `wvsetup` under the company organization when the org is ready.
- [ ] Confirm Google Workspace admin access for `warreandvavasour.com`.
- [ ] Confirm Hugging Face org and token naming.
- [ ] Decide which WorkspaceAlberta repos move from personal ownership to company ownership.
- [ ] Keep the public WorkspaceAlberta README focused on procurement value and the product surface.
- [ ] Keep private account inventory in `wvsetup`, not in WorkspaceAlberta.
- [ ] Run `python -m unittest tests.test_canadabuys_mcp_smoke` after server, config, or agent setup changes.
- [ ] Sync GBrain after visible doc or agent setup changes.

## Operating Rules

- Treat CanadaBuys and Alberta Purchasing Connection as the primary working integration.
- Treat MCP as the practical connection layer, not abstract infrastructure.
- Keep `wvsetup` private until corporate account setup is safe to expose or transfer.
- Confirm before running commands that mutate external accounts, organizations, repos, billing, DNS, OAuth apps, or provider settings.
- Keep OpenAI/Codex setup separate from the Build Canada procurement MCP logic.
- Keep customer-facing copy in the existing "Wouldn't it be great if..." voice.

## Regular Commands

From WorkspaceAlberta:

```powershell
python -m unittest tests.test_canadabuys_mcp_smoke
```

From `wvsetup`:

```powershell
python scripts/print_checklist.py
```

On Windows PowerShell, use UTF-8 mode if the console rejects Unicode output:

```powershell
python -X utf8 scripts\print_checklist.py
```

If `scripts/print_checklist.py` reports that `PyYAML` is missing, install it in the local environment used for setup work:

```powershell
python -m pip install pyyaml
```
