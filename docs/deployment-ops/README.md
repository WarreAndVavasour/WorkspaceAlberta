# WorkspaceAlberta Deployment Ops

Operational runbooks for leased WorkspaceAlberta terminals deployed to customer sites.

The deployment model assumes WorkspaceAlberta owns the equipment. Customers pay for setup, onboarding, monthly service, and continued access. If the subscription ends, the equipment is returned, wiped, refurbished, and redeployed.

## Start Here

**[pi-out-of-box-setup.md](pi-out-of-box-setup.md)** — Master guide for first-time Raspberry Pi setup. Covers everything from unboxing to a working CEO stack. Start here if you are new to Raspberry Pi.

## Files

- [pi-out-of-box-setup.md](pi-out-of-box-setup.md): master out-of-box guide — hardware checklist, flashing the OS, first boot, and running the installer.
- [ceo-pi-setup.md](ceo-pi-setup.md): software installer reference for CEO productivity terminals (Codex, ChatGPT Desktop, OpenCode, Tailscale). Assumes the OS is already installed.
- [tailscale-pi-remote-support.md](tailscale-pi-remote-support.md): how to prepare Raspberry Pi terminals before deployment and connect later with Tailscale SSH + tmux.
- [commercial-licensing-notes.md](commercial-licensing-notes.md): practical licensing notes for Hermes Agent and Cohere in a commercial WorkspaceAlberta subscription.

## Operating principle

Do not ask customers to become system administrators.

Each deployed terminal should be reachable through a private management plane before it leaves our hands. The customer should never need to open router ports, expose SSH to the internet, or troubleshoot package updates. Remote support should be boring:

1. Find the device by hostname.
2. Connect through Tailscale.
3. Attach a tmux session.
4. Repair, update, reboot, or inspect logs.
5. Record what changed.

## Subscriber key on every terminal

A terminal is not billable until it carries a subscriber key. The hosted endpoint
gates bid rooms, Cohere tender review, the watchlist, and bid/no-bid scorecards on
an `Authorization: Bearer wa_live_...` header; without one the customer sees the
free tier and none of what they are leasing the box for.

Provision it during staging, after the software installer and before shipping:

```bash
WA_API_KEY=wa_live_... ./installer/configure-subscriber-key.sh
```

The script verifies the key against `GET /me` before writing, so a typo or an
inactive subscription fails on the bench rather than at the customer's desk. It
writes `~/.config/workspacealberta/credentials` at mode 600 and registers the
authenticated endpoint with the CLIs on the box.

Confirm before the terminal leaves:

```bash
curl -H "Authorization: Bearer $(sed -n 's/^WA_API_KEY=//p' ~/.config/workspacealberta/credentials)" \
  https://elbowsupknivesout.warreandvavasour.com/me
```

Expect `200` with `"status": "active"`.

**Known limitation.** Keys are per *subscriber*, not per device. A customer with
two terminals runs the same key on both, and revoking a returned terminal revokes
the customer's whole subscription. Until per-device keys land, treat key rotation
as a customer-level operation and coordinate it with the customer.

## Naming convention

Use one hostname everywhere: physical label, OS hostname, Tailscale machine name, inventory, and customer record.

Format:

```text
wa-pi5-<customer>-<site>-<nn>
```

Examples:

```text
wa-pi5-acme-edmonton-01
wa-pi5-demo-lab-01
```
