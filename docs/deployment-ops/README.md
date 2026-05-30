# WorkspaceAlberta Deployment Ops

Operational runbooks for leased WorkspaceAlberta terminals deployed to customer sites.

The deployment model assumes WorkspaceAlberta owns the equipment. Customers pay for setup, onboarding, monthly service, and continued access. If the subscription ends, the equipment is returned, wiped, refurbished, and redeployed.

## Files

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
