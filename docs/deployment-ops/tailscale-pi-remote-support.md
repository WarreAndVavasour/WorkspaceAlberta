# Tailscale Raspberry Pi Remote Support Runbook

This runbook prepares leased Raspberry Pi terminals so WorkspaceAlberta can connect remotely for repairs, updates, reboots, log review, and customer support.

Use Tailscale as the private management plane. Do not expose public SSH and do not ask customers for router port forwarding.

## Operating model

- Each Pi joins the WorkspaceAlberta Tailscale tailnet before shipping.
- Each Pi is a tagged, non-user device.
- Access is controlled in the Tailscale policy file.
- Support connects by MagicDNS hostname or Tailscale IP.
- Long-running work happens inside tmux so dropped connections do not kill updates.
- Shipped devices should not use ephemeral auth keys. Ephemeral nodes disappear after going offline.

Recommended tags:

```text
tag:wa-terminal
tag:wa-pi5
```

Recommended support user:

```text
support
```

## One-time tailnet setup

In the Tailscale admin console, create ACL/policy entries for support users and WorkspaceAlberta device tags.

Example policy fragment:

```jsonc
{
  "groups": {
    "group:support": [
      "owner@example.com",
      "tech1@example.com"
    ]
  },
  "tagOwners": {
    "tag:wa-terminal": ["group:support"],
    "tag:wa-pi5": ["group:support"]
  },
  "acls": [
    {
      "action": "accept",
      "src": ["group:support"],
      "dst": ["tag:wa-terminal:*", "tag:wa-pi5:*"]
    }
  ],
  "ssh": [
    {
      "action": "check",
      "src": ["group:support"],
      "dst": ["tag:wa-terminal", "tag:wa-pi5"],
      "users": ["support", "autogroup:nonroot"]
    }
  ]
}
```

Notes:

- Tailscale SSH users must already exist on the Pi.
- Prefer `check` mode for support access so staff must re-authenticate.
- Keep `tagOwners` tight. A user or auth key that can apply a tag can grant that device the tag identity.
- If root access is truly needed, add it deliberately and use `check` mode.

## Provisioning auth keys

Create short-lived Tailscale auth keys for staging batches.

Recommended settings:

- Reusable: yes for a provisioning batch; no for one-off device.
- Pre-approved: yes if device approval is enabled.
- Ephemeral: no for shipped terminals.
- Tags: `tag:wa-terminal`, `tag:wa-pi5`.
- Expiration: short, usually 1 to 7 days.

Do not commit auth keys to Git. Do not bake reusable keys into a golden image. Do not leave auth keys on shipped devices.

## Per-device pre-shipping setup

Set variables:

```bash
export HOSTNAME_FQ="wa-pi5-acme-edmonton-01"
export SUPPORT_USER="support"
```

Update the OS and install base tools:

```bash
sudo apt-get update
sudo apt-get full-upgrade -y
sudo apt-get install -y curl ca-certificates tmux vim git htop jq unattended-upgrades
sudo systemctl enable --now unattended-upgrades
```

Set hostname:

```bash
sudo hostnamectl set-hostname "$HOSTNAME_FQ"
hostnamectl
hostname
```

Create support user:

```bash
sudo adduser --disabled-password --gecos "WorkspaceAlberta Support" "$SUPPORT_USER"
sudo usermod -aG sudo "$SUPPORT_USER"
```

Optional passwordless sudo, only if operationally required:

```bash
printf '%s ALL=(ALL) NOPASSWD:ALL\n' "$SUPPORT_USER" | sudo tee "/etc/sudoers.d/90-$SUPPORT_USER"
sudo chmod 0440 "/etc/sudoers.d/90-$SUPPORT_USER"
sudo visudo -c
```

Install Tailscale using the official Linux installer:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
systemctl status tailscaled --no-pager
```

Join the tailnet with hostname, tags, and Tailscale SSH:

```bash
sudo install -m 0600 /dev/null /root/tailscale-authkey
sudo nano /root/tailscale-authkey

sudo tailscale up \
  --auth-key=file:/root/tailscale-authkey \
  --hostname="$HOSTNAME_FQ" \
  --advertise-tags=tag:wa-terminal,tag:wa-pi5 \
  --ssh

sudo shred -u /root/tailscale-authkey
```

Interactive alternative:

```bash
sudo tailscale up \
  --hostname="$HOSTNAME_FQ" \
  --advertise-tags=tag:wa-terminal,tag:wa-pi5 \
  --ssh
```

Important: if re-running `tailscale up`, include all desired non-default flags again.

## Verify before shipping

On the Pi:

```bash
tailscale status
tailscale ip -4
tailscale netcheck
systemctl is-active tailscaled
```

From a support workstation:

```bash
tailscale status | grep "$HOSTNAME_FQ"
tailscale ping "$HOSTNAME_FQ"
tailscale ssh support@"$HOSTNAME_FQ"
```

Inside the remote shell:

```bash
whoami
hostname
sudo true
```

Confirm in the Tailscale admin console:

- Device name matches the physical label.
- Device has expected tags.
- Tailscale SSH is enabled.
- Device is approved if approval is enabled.
- Machine is not owned by an unintended user identity.

## tmux support convention

Create or attach to the standard support session immediately after connecting:

```bash
tmux attach -t support || tmux new -s support
```

Recommended session names:

```text
support   general incident/support work
update    OS/package/app updates
app       application logs/restarts
customer  live customer-assisted session
```

Useful tmux commands:

```bash
tmux ls
tmux new -s support
tmux attach -t support
tmux new -s update
```

Detach with `Ctrl-b`, then `d`.

## Connecting after deployment

Find and test reachability:

```bash
tailscale status
tailscale status | grep wa-pi5-acme-edmonton-01
tailscale ping wa-pi5-acme-edmonton-01
```

Connect:

```bash
tailscale ssh support@wa-pi5-acme-edmonton-01
```

If MagicDNS is unavailable, use the Tailscale IP from the admin console:

```bash
tailscale ssh support@100.x.y.z
```

Fallback with OpenSSH over the Tailscale network only if sshd is installed and allowed:

```bash
ssh support@wa-pi5-acme-edmonton-01
ssh support@100.x.y.z
```

## Standard remote triage

```bash
hostnamectl
date
uptime
tailscale status
tailscale netcheck
tailscale ip -4
ip addr
ip route
systemctl --failed --no-pager
df -h
free -h
vcgencmd measure_temp 2>/dev/null || true
journalctl -p warning -n 100 --no-pager
```

Tailscale checks:

```bash
systemctl status tailscaled --no-pager
journalctl -u tailscaled -n 200 --no-pager
sudo tailscale debug prefs 2>/dev/null || true
```

Application checks:

```bash
systemctl status <service-name> --no-pager
journalctl -u <service-name> -n 200 --no-pager
sudo systemctl restart <service-name>
```

Discover likely services:

```bash
systemctl list-units --type=service --state=running --no-pager
systemctl list-unit-files --type=service --no-pager | grep -Ei 'workspace|alberta|kiosk|terminal|chrom|browser|docker|tailscale'
```

## Safe update and reboot workflow

Use tmux and coordinate with the customer before rebooting.

```bash
tmux attach -t update || tmux new -s update
sudo apt-get update
apt list --upgradable
sudo apt-get full-upgrade -y
sudo apt-get autoremove -y
sudo systemctl --failed --no-pager
```

Check if reboot is required:

```bash
if [ -f /var/run/reboot-required ]; then cat /var/run/reboot-required; fi
```

If approved, reboot:

```bash
sudo systemctl reboot
```

Watch for return:

```bash
tailscale ping wa-pi5-acme-edmonton-01
```

Reconnect:

```bash
tailscale ssh support@wa-pi5-acme-edmonton-01
tmux attach -t update || tmux attach -t support || true
```

## Tailscale repair

If reachable by another method but Tailscale is unhealthy:

```bash
sudo systemctl restart tailscaled
systemctl status tailscaled --no-pager
tailscale status
tailscale netcheck
```

If registration is lost and someone has local/customer-assisted shell access, use a fresh short-lived auth key:

```bash
sudo tailscale up \
  --auth-key=<fresh-key> \
  --hostname=wa-pi5-acme-edmonton-01 \
  --advertise-tags=tag:wa-terminal,tag:wa-pi5 \
  --ssh
```

Use `--reset` only when intentionally reapplying the full desired state:

```bash
sudo tailscale up --reset \
  --auth-key=<fresh-key> \
  --hostname=wa-pi5-acme-edmonton-01 \
  --advertise-tags=tag:wa-terminal,tag:wa-pi5 \
  --ssh
```

## Customer-assisted offline workflow

If the Pi is absent from Tailscale:

1. Check Tailscale admin console last-seen time.
2. Ask customer to verify power, Ethernet/Wi-Fi, display, and upstream internet.
3. Ask customer to power-cycle the Pi once.
4. Keep a ping running:

```bash
tailscale ping wa-pi5-acme-edmonton-01
```

When it returns:

```bash
tailscale ssh support@wa-pi5-acme-edmonton-01
journalctl -b -1 -p warning --no-pager | tail -200
journalctl -u tailscaled -b -1 --no-pager | tail -200
```

## Return, cancellation, and redeployment

When equipment comes back:

1. Disable or remove the Tailscale machine in the admin console.
2. Wipe/reimage the Pi.
3. Remove customer credentials and cached data.
4. Inspect hardware, cables, labels, and power supply.
5. Re-provision under a new hostname before redeployment.

## Security cautions

- Do not commit auth keys, passwords, recovery codes, or customer-sensitive inventory.
- Use short-lived provisioning keys.
- Rotate or revoke provisioning keys after each batch.
- Prefer tagged devices for leased terminals.
- Keep `tagOwners` limited.
- Prefer Tailscale SSH with `check` mode.
- Do not open public SSH.
- Do not request customer router port forwards.
- Disable or change all default passwords.
- Keep Linux users minimal.
- Reimage devices before redeployment.
