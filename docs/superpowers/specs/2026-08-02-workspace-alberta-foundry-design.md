# Workspace Alberta Foundry Design

Status: approved design, 2026-08-02

## Summary

Workspace Alberta Foundry turns a Raspberry Pi 5 into the always-on control plane for the Warre & Vavasour repository portfolio. The Pi is the durable operator, memory, scheduler, audit system, private access point, and physical terminal. It delegates bounded build jobs to Claude Code workers running in isolated local worktrees, containers, E2B sandboxes, or GitHub Actions.

The operating mode is **Full Sovereign**. Within an explicit repository allowlist, the Foundry may select work, implement changes, push branches, approve and merge its own pull requests, deploy, verify production health, and roll back without waiting for human approval. This authority is constrained by signed per-repository policy, deterministic promotion gates, limited credentials, budgets, immutable prohibitions, and an append-only audit ledger.

The first launch uses a 64 GB microSD card. A future USB 3 SSD is rebuilt with the same idempotent installer rather than cloned from the card. The microSD then becomes offline recovery media.

## Objectives

1. Convert a fresh Raspberry Pi OS installation into `wa-foundry-01` through a repeatable, verified installer.
2. Keep Hermes available continuously for memory, scheduling, messaging, portfolio context, and operator interaction.
3. Use fresh, bounded Claude Code sessions for implementation instead of one indefinitely growing model conversation.
4. Treat WorkspaceAlberta as both the product repository and an installed MCP tool available to the Foundry.
5. Operate an allowlisted portfolio of Alberta and Warre & Vavasour repositories autonomously.
6. Provide private remote administration through Tailscale without public SSH or router port forwarding.
7. Expose a Bloomberg-terminal-style command centre showing work, evidence, costs, deployments, and system health.
8. Survive worker failures, model errors, reboots, network outages, and failed deployments without losing control-plane state.
9. Make migration from microSD to USB SSD a clean reprovisioning exercise.

## Non-goals

- Running Gemma or another local general-purpose language model.
- Treating the Pi as the primary build server for every workload.
- Using the SupTronics X1002 NVMe shield at the same time as the AI HAT+ 2.
- Installing the Coral Edge TPU on the Foundry Pi.
- Allowing the Foundry to expand its own authority, acquire new credentials, or change its Tailscale policy.
- Replacing existing hosted WorkspaceAlberta services or procurement logic.
- Hiding Hermes, Claude Code, or other upstream components behind misleading white-label claims.

## Approved decisions

| Area | Decision |
|---|---|
| Product | Workspace Alberta Foundry, the Warre & Vavasour command centre |
| Device | `wa-foundry-01` |
| Mode | Full Sovereign |
| Topology | Distributed Shipyard |
| Host OS | Raspberry Pi OS with Desktop, 64-bit Trixie |
| Stage 0 storage | Existing 64 GB PiShop microSD, freshly imaged |
| Stage 1 storage | External USB 3 SSD with UASP, 1 TB recommended |
| Private network | Tailscale on the host, with Tailscale SSH |
| Primary accelerator | Raspberry Pi AI HAT+ 2 / Hailo-10H |
| Local models | Out of scope |
| Coral hardware | Future independent Scout node |
| General planner | Persistent Hermes profile and gateway |
| Code workers | Programmatic Claude Code sessions |
| Worker locations | Local container/worktree, E2B, or GitHub Actions |
| Promotion | Autonomous PR, merge, deploy, verify, and rollback inside policy |

## Hardware topology

### Foundry node

- Raspberry Pi 5 with 16 GB RAM.
- Raspberry Pi Active Cooler and the AI HAT+ 2 heatsink.
- Raspberry Pi AI HAT+ 2 connected to the Pi 5 PCIe interface.
- Official 27 W power supply.
- Existing 64 GB microSD for Stage 0.
- Future external USB 3 SSD for Stage 1.
- Ethernet preferred for commissioning; Wi-Fi remains configured as fallback.

The AI HAT+ 2 owns the Pi's external PCIe connection. The X1002 NVMe shield must remain disconnected. Physical stacking does not provide a second PCIe lane.

### Reserve hardware

- SupTronics X1002 V1.1 NVMe shield: reserved for a storage-focused Pi build.
- Pineberry Pi Hat AI! Coral carrier: reserved for a future Scout node.
- Required Coral module if recovered or purchased: Google Coral M.2 Accelerator A+E key, 2230, part `G650-04527-01`.

The Coral carrier and Hailo HAT cannot run together on this Pi because both require the external PCIe interface.

## System architecture

```text
Laptop / phone
      |
      | private Tailscale network
      v
+------------------------------------------------+
| Raspberry Pi 5: sovereign control plane        |
|                                                |
| Raspberry Pi OS 64-bit Trixie                  |
| Tailscale + systemd health services            |
| Hermes memory, schedules, messaging, MCP       |
| Portfolio manifest + Charters + Ledger         |
| Workspace Alberta Foundry Terminal             |
+----------------------+-------------------------+
                       | bounded job dispatch
             +---------+-----------+
             |                     |
             v                     v
     Local worktree/container   E2B sandbox
             |                     |
             +----------+----------+
                        |
                        v
                  GitHub Actions
                        |
                        v
             Claude Code build workers
                        |
                        v
       test -> review -> merge -> deploy -> verify
                        |
                        v
             Ledger + Hermes memory + Terminal
```

The control plane stays alive when a worker crashes. A worker never becomes the authority source; it receives a job-specific capability and returns evidence. Persistent intent and history live in structured state, Hermes memory, Git, and the Ledger.

## Components and boundaries

### Host foundation

The host foundation owns the OS, storage, Tailscale, time synchronization, updates, Docker or Podman, system users, systemd services, thermal monitoring, disk monitoring, and recovery commands. It does not choose portfolio work.

Tailscale runs on the host rather than inside a worker container. The Foundry remains reachable when Hermes, Docker, the Terminal, or an individual repository is broken.

### Foundry installer and CLI

The existing Pi appliance installer becomes an idempotent Foundry installer rather than a one-shot dashboard setup script. It exposes a small operator CLI, `wa`, with stable commands:

- `wa doctor`: verify hardware, network, credentials, services, workers, and repositories.
- `wa status`: summarize controller and portfolio state.
- `wa hold`: stop new jobs and deployments while monitoring continues.
- `wa arm`: allow policy-compliant autonomous work.
- `wa recover`: restore services and state from a known-good configuration.
- `wa migrate`: export/import encrypted configuration and Ledger state for SSD reprovisioning.

Repeated installation must converge without duplicating services, profiles, cron entries, repository records, or secrets.

### Hermes controller

Hermes provides the always-on gateway, model access, schedules, messaging, memory, skills, MCP tools, and operator conversation. A dedicated `workspace-alberta-foundry` profile owns its configuration and personality.

Hermes is not the shell authority for every repository. It creates structured jobs and sends them to the dispatcher. This keeps conversational state separate from build state and permits deterministic enforcement between planning and execution.

### Workspace Alberta tool layer

WorkspaceAlberta is installed as a local development checkout and connected as an MCP tool. The local stdio server is used for development and offline smoke tests. The hosted MCP endpoint remains a production fallback and external product surface.

Procurement, bid-room, OPERA, and future Alberta intelligence tools remain bounded modules. Foundry orchestration must not be inserted into `procurement_core` or the transport adapters.

### Portfolio manifest

The portfolio manifest is the allowlist and routing index. Every repository entry has:

- stable repository ID, GitHub origin, and local mirror path;
- mission and current product state;
- enabled signal sources;
- test, build, deploy, health-check, and rollback commands;
- worker backend preferences;
- risk class, concurrency cap, and daily budget;
- Charter location and signature;
- ownership and credential references;
- current operating state: observe, armed, held, or quarantined.

Initial candidate repositories include WorkspaceAlberta, AlbertaGas, AlbertaLidar, RealEstate, AutoScientist/Volume2Gym, and other repositories added manually by the owner. Discovery does not imply authority: an unlisted repository is read-only and cannot be changed.

### Repository Charter

Each allowlisted repository has a versioned, owner-approved Charter defining:

- permitted branches, paths, actions, and deployment targets;
- required test suites and evidence;
- budget and concurrency limits;
- risk classification and required review depth;
- health checks and rollback procedure;
- permanent prohibitions.

Workers cannot edit the effective Charter used for their own job. Charter changes require an owner-signed update outside the autonomous promotion path.

Charters are signed on an owner workstation with an SSH signing key. The Pi stores only the corresponding public verification key in a root-owned path. `wa arm` refuses to arm a repository when its Charter or signature is missing, invalid, expired, or names a different repository. Neither the controller identity nor any worker receives the owner's signing private key.

Risk classes are explicit:

| Class | Authority |
|---|---|
| Observe | Read and propose only; no repository writes |
| Build | Branches, tests, artifacts, and PRs; no deployment |
| Stage | Build authority plus named non-production deployments |
| Production | Stage authority plus reversible deployment to named production targets |

Destructive production-data operations remain forbidden in every class unless the owner issues a separate, single-purpose signed capability with an expiry and exact target.

### Dispatcher and workers

The dispatcher turns a structured job into the least-powerful suitable worker:

- local worktree and hardened container for small compatible jobs;
- E2B for risky files, heavier tools, or clean cloud compute;
- GitHub Actions for repository-native CI, scheduled maintenance, and deployment;
- later remote workers reached through SSH or another supported Hermes backend.

Claude Code runs in a fresh bounded session for each implementation or review job. Job context contains the repository Charter, scoped task, relevant project instructions, completion contract, budget, and allowed tools. It does not contain unrelated secrets or the entire portfolio history.

### Ledger

The Ledger is append-only operational evidence. Each job records:

- signal and selected objective;
- plan and model/session identifiers;
- worker backend, tool calls, duration, and cost;
- commit and diff identifiers;
- test, review, and policy-gate evidence;
- PR, merge, deployment, health, and rollback results;
- final state and any learned repository facts.

Secrets, raw credentials, and full sensitive prompts are redacted before persistence. The Foundry can append to the Ledger but cannot rewrite or disable prior records.

The Ledger runs as a separate least-privileged service. Controllers and workers submit entries through an append-only local socket and have no direct write access to prior records. Entries form a hash chain. A root-owned checkpoint service periodically signs the current chain head and copies the checkpoint to a remote owner-controlled location. Loss of the Ledger service, a broken hash chain, or failed checkpointing places the Foundry in automatic hold.

### Foundry Terminal

The dedicated dual-display interface follows the existing industrial-executive terminal specification. It is keyboard-first and includes:

- **Opening Bell:** daily portfolio brief, deadlines, failures, and opportunities.
- **Portfolio Radar:** state, risk, revenue evidence, and next best work by repository.
- **Shipyard:** active plans, workers, tests, queues, and deployment stages.
- **Activity Tape:** continuous event stream for commits, costs, releases, and alerts.
- **Ledger:** drill-down evidence for every autonomous decision.
- **Systems:** Pi temperature, storage, Hailo, Tailscale, Hermes, workers, and cloud health.

The local dashboard binds to loopback. Remote viewing uses private Tailscale access, not a public listener or Tailscale Funnel.

### Hailo role

The Hailo-10H is not used as the Foundry's language model. It remains available for later always-on visual or sensor workloads: camera event detection, document intake, workspace presence, equipment monitoring, or physical alarms. Hailo support is verified during commissioning, but sensing features are a later milestone and cannot block the control-plane launch.

## Autonomous operating loop

```text
signals
  -> normalize and deduplicate
  -> score expected value, urgency, risk, and cost
  -> create bounded job
  -> policy preflight
  -> isolated implementation
  -> deterministic tests
  -> independent adversarial review
  -> PR and CI evidence
  -> autonomous merge
  -> canary deployment
  -> health verification
  -> promote or rollback
  -> Ledger entry and Hermes memory update
```

Signals may come from repository CI, issues, dependency alerts, approved backlogs, production telemetry, scheduled research, WorkspaceAlberta opportunities, or Hermes cron jobs. External text is untrusted input. It can suggest work but cannot alter Charters, credentials, budgets, or promotion gates.

The selector favors measurable work that advances a repository's documented product state. It avoids cosmetic churn, repeated rewrites, and work without a verifiable completion condition.

## Full Sovereign authority

Within an armed repository's Charter, the Foundry may:

- create and prioritize tasks;
- modify files in isolated branches or worktrees;
- run tests and build artifacts;
- push branches and open pull requests;
- review and approve its own pull requests through an independent worker;
- merge after all required gates pass;
- deploy to named targets;
- verify health, promote canaries, and roll back;
- create issues or Ledger follow-ups for unresolved work.

The Foundry may never:

- delete a repository or rewrite published Git history;
- expand its repository allowlist or its own Charter authority;
- modify or disable the Ledger and hold mechanisms;
- export, print, commit, or transmit secrets outside their declared service;
- change Tailscale grants, tags, administrators, or Tailnet Lock;
- modify billing ownership, payment methods, identity-provider ownership, or account recovery settings;
- bypass failing tests, review, budget, health, or rollback gates;
- perform destructive production data migrations without a separately signed capability.

External mutations not described by a repository Charter remain out of scope even when a worker technically has a tool capable of performing them.

## Brakes and recovery

### Automatic hold

The controller enters hold when it detects:

- repeated failure or rollback loops;
- missing or invalid Charter signatures;
- failed required tests or health checks;
- budget or concurrency breaches;
- suspicious instructions attempting to change authority or expose secrets;
- unavailable audit storage;
- critical disk, temperature, power, clock, or network-health conditions.

Monitoring and remote access continue in hold. New build and deployment jobs do not start.

### Remote hold

The owner can run `wa hold` over Tailscale. Tailscale administrator credentials are never stored on the Pi, so the Foundry cannot grant itself new network access.

### Physical Deadman

A guarded GPIO key switch is a later terminal-hardware enhancement. Disarming it maps to the same durable hold state. The software hold and automatic hold are required at Stage 0; the physical switch is not required to commission the microSD system.

### Failure and rollback behavior

- Worker failure: terminate or quarantine the worker, preserve evidence, and leave the controller running.
- Test failure: do not merge; create a bounded repair attempt only within the retry budget.
- Deployment failure: execute the repository rollback command and verify the previous version.
- Health uncertainty: fail closed and hold that repository's deployments.
- Network outage: continue local monitoring and queue cloud work without repeated retries.
- Disk pressure: stop new work, prune only declared caches, and preserve Git and Ledger state.
- Hermes failure: systemd restarts the profile; `wa doctor` remains independently available.
- Controller corruption: boot the recovery microSD or rerun the installer, then import encrypted state.

## Credentials and trust boundaries

Commissioning includes interactive sign-in for Tailscale, GitHub CLI, Claude Code/Anthropic, Hermes model providers, and the cloud services required by armed repositories.

Principles:

- no credential is committed to Git or baked into the image;
- service files are readable only by the dedicated Foundry identity;
- workers receive only job-scoped environment variables or short-lived credentials;
- OIDC and provider-native short-lived credentials are preferred for CI and deployment;
- no Tailscale admin, billing-owner, domain-owner, or account-recovery credential is stored on the Pi;
- logs and Ledger entries redact known secret formats and declared secret variables;
- external documents, issues, and web pages are data, never authority.

## Stage 0: microSD commissioning

1. Use Raspberry Pi Imager to write Raspberry Pi OS with Desktop, 64-bit Trixie, to the 64 GB card.
2. Preconfigure hostname `wa-foundry-01`, locale, time zone, Wi-Fi fallback, a non-default administrator, and SSH-key authentication.
3. Boot with Ethernet when available, the official power supply, active cooling, and AI HAT+ 2. Keep X1002 and Coral hardware disconnected.
4. Update Raspberry Pi OS and EEPROM, reboot, and verify power, thermal, storage, time, and network health.
5. Install the AI HAT+ 2 package `hailo-h10-all`, reboot, and verify with `hailortcli fw-control identify`.
6. Install Tailscale on the host, enroll `wa-foundry-01`, enable Tailscale SSH, apply the owner-managed `tag:wv-foundry`, and verify remote recovery access.
7. Install WorkspaceAlberta and run the Foundry installer.
8. Complete the local credential ceremony without displaying or recording secret values.
9. Run commissioning tests.
10. Run `wa arm` only after every required gate is green.

The exact Raspberry Pi Imager and shell instructions belong in the implementation runbook generated from this design. The installer must not assume the preloaded PiShop image is current.

## Stage 1: USB SSD migration

1. Export encrypted Foundry configuration and Ledger state with `wa migrate`.
2. Use Raspberry Pi Imager to write the same approved Raspberry Pi OS release directly to a UASP-capable USB 3 SSD.
3. Boot the Pi from the SSD with the microSD removed.
4. Rerun the idempotent Foundry installer.
5. Import the encrypted state and repeat the full commissioning suite.
6. Confirm the root filesystem is on the USB SSD, test reboot and power-loss recovery, and then arm the Foundry.
7. Reimage or verify the microSD as a minimal known-good recovery system, label it `FOUNDRY RECOVERY`, and store it offline.

Cloning the live microSD is not the standard migration path. Clean reprovisioning proves that the installer and recovery process work.

## Verification and acceptance

### Host and installer

- A clean 64-bit Trixie image reaches a healthy Foundry through the documented procedure.
- Running the installer twice produces no duplicate or destructive changes.
- All required services survive reboot and recover from forced process termination.
- `wa doctor` reports actionable failures without requiring Hermes.
- Tailscale SSH works before and after a local network change.
- The dashboard and APIs are not publicly reachable.
- Hailo identification passes without enabling local language-model workloads.

### Worker isolation

- A deliberately malicious or broken test job cannot modify the host, another repository, Charters, or the Ledger.
- A killed worker leaves the controller healthy and its worktree quarantined or cleaned according to policy.
- Secrets do not appear in worker transcripts, Git diffs, process arguments, or Ledger records.

### Promotion and rollback

- A known-good fixture change completes plan, build, tests, review, PR, merge, canary, health check, and Ledger recording.
- A failing test cannot be overridden by the model.
- A forced canary-health failure automatically restores the previous version.
- Repeated failure enters hold and stops new jobs.

### Sovereign controls

- An unlisted repository cannot be changed.
- A worker cannot change its own effective Charter.
- Budget exhaustion prevents additional paid jobs.
- `wa hold` stops new jobs and deployments while monitoring and Tailscale remain available.
- Reboot preserves armed or held state deliberately rather than defaulting silently.

### Storage migration

- Encrypted configuration and Ledger state export and import successfully.
- A clean SSD installation reaches the same acceptance state without cloning the microSD.
- The recovery card can restore operator access after simulated root-drive failure.

## Implementation decomposition

This design is intentionally implemented as bounded milestones. Each milestone receives its own implementation plan and verification evidence.

1. **Stage 0 host foundation:** Raspberry Pi Imager runbook, Trixie bootstrap, Tailscale, Hailo verification, idempotent installer foundation, `wa doctor/status/hold/arm`, systemd, and recovery documentation.
2. **Portfolio control plane:** manifest, signed Charters, Ledger, structured jobs, budgets, signal normalization, and Hermes Foundry profile.
3. **Distributed workers and promotion:** worktrees, containers, E2B/GitHub Actions dispatch, Claude Code sessions, reviews, CI gates, deployment, health checks, and rollback.
4. **Foundry Terminal:** Opening Bell, Portfolio Radar, Shipyard, Activity Tape, Ledger, and Systems surfaces in the established terminal visual language.
5. **Hailo sensing:** opt-in local vision and physical event inputs that emit structured signals to the controller.
6. **Coral Scout:** a separate Tailscale-connected Pi using the Pineberry carrier and a compatible Coral A+E-key module.

The first implementation plan covers milestone 1 only. Later milestones must not be smuggled into the bootstrap script.

## Primary technical references

- Raspberry Pi getting started and Imager: <https://www.raspberrypi.com/documentation/computers/getting-started.html>
- Raspberry Pi USB mass-storage boot: <https://www.raspberrypi.com/documentation/hardware/displays/raspberry-pi-5.html>
- Raspberry Pi AI HAT+ 2: <https://www.raspberrypi.com/documentation/accessories/ai-hat-plus.html>
- Raspberry Pi AI software: <https://www.raspberrypi.com/documentation/computers/ai.html>
- Claude Code programmatic operation: <https://code.claude.com/docs/en/headless>
- Claude Code installation: <https://code.claude.com/docs/en/installation>
- Hermes Agent: <https://github.com/NousResearch/hermes-agent>
- Hermes terminal backends: <https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/configuration.md>
- Tailscale server provisioning: <https://tailscale.com/kb/1245/set-up-servers>
- Tailscale policy syntax: <https://tailscale.com/kb/1337/policy-syntax>
- SupTronics X1002: <https://suptronics.com/Raspberrypi/Storage/x1002-v1.1.html>
- Coral M.2 Accelerator datasheet: <https://www.coral.ai/static/files/Coral-M2-datasheet.pdf>
