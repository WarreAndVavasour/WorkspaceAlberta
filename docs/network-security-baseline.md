# Network security baseline

Review date: 2026-10-25. Source reviewed: corporate main commit
`d84256aa26b61cb74e819d6b3a71238f764f6c64`.

Reference: NSA, *Network Infrastructure Security Guide*, October 2023, version 1.2,
U/OO/118623-22 / PP-22-0293. The supplied filename contains 20220615, but its cover
and revision history identify the October 2023 edition. Section numbers below refer
to that edition. This is a targeted source/configuration review, not a compliance
certification, complete vulnerability scan or live infrastructure assessment.
The Codex Security workflow's referenced preflight resources were unavailable in
this session, so an automated Codex Security scan was not completed.

## NSA cybersecurity implementation note

This change adopts selected principles from the NSA Network Infrastructure Security
Guide: least privilege, restricted management access, segmentation, secure protocols,
and evidence-based operational checks. It implements those principles in repository
provisioning guidance and the control checklist. It does not apply a live tailnet
policy, firewall, account change or cloud configuration. Open controls below remain
unverified until deployment operators collect the stated evidence. This is not NSA
certification, endorsement or a claim of complete guide compliance.

## Boundaries that matter

The public procurement endpoint is intentionally reachable by internet clients.
Tailscale protects the Pi management plane; it does not automatically protect the
public API, customer Ethernet/Wi-Fi, Cloud Run, Supabase, or provider API calls.
Application authentication remains necessary inside a private network.

Keep four boundaries distinct: public API ingress, private terminal management,
customer-local devices/data, and outbound provider/document traffic. A terminal
must not become a bridge between customers or between public API traffic and the
management network. Do not join the public server to a broadly permissive tailnet
without a separately reviewed need and narrowly scoped policy.

## Control map

"Present" means a control exists in reviewed source, not that production settings
were inspected. "Open" means evidence or implementation is still needed.

| NSA principle | Repository evidence | Status and required adoption |
|---|---|---|
| Segmentation and necessary ports only, sections 2.1-2.4 | `docs/deployment-ops/tailscale-pi-remote-support.md` previously allowed all terminal ports | Revised example grants support TCP 22 only. Remove overlapping permissive grants/ACLs in the actual policy. Verify terminal-to-terminal and non-support denials. Live status open. |
| No backdoor connections, sections 2.3, 2.6 | Pi runbook says no public SSH or router forwarding | Intent present. Verify LAN/IPv6 firewall, OpenSSH listeners, device sharing, Funnel, subnet routes and exit nodes. A tailnet policy cannot filter direct LAN access. |
| Network admission and restricted VPN, sections 2.5-2.6 | Device tags and short-lived provisioning keys in runbook | Partial. Verify device approval, SSO/MFA, lost-device removal, support workstation posture, and tagged-device key-expiry policy. Enrollment-key expiry is not device removal. |
| Software/configuration integrity, sections 3.1-3.4 | Deployment workflow pins core Actions by SHA, builds tracked files, deploys an image digest; Pi runbook enables unattended upgrades | Partial. Python dependency ranges and base-image tag are not immutable. Add a reviewed dependency locking/update process, image scanning, supported OS inventory and restoration checks. Do not freeze vulnerable versions indefinitely. |
| Authentication, authorization, accounting, sections 4.1-4.6 | `identity.check_tool_access`, tenant context in `storage.py`, OAuth validation and per-instance rate limits | Present in source. Verify hosted flags, identity provider MFA, failed-login alerts and distributed edge limits. Tailnet identity does not replace API tool authorization. |
| Least privilege, section 4.5; local accounts, section 5 | Docker runs UID 10001; prior Pi example allowed any non-root SSH user and optional `NOPASSWD:ALL` | Non-root container present. Revised Pi instructions permit `support` only, no default sudo membership and no blanket sudoers rule. Live sudoers/account review open. |
| Remote logging and time, sections 6.1-6.4 | `http_hardening.security_event` / `telemetry.py`; Pi examples read local journal | Partial. Verify off-device collection, retention, alert delivery and log access. Capture support identity, destination, elevation, policy changes and revocations without tokens/customer documents. Verify clock synchronization on every device. |
| Secure remote services, sections 7.1-7.4, 7.9, 7.11 | Public URLs use HTTPS; SMTP STARTTLS uses a verified SSL context; Tailscale SSH documented | Source controls present. Verify TLS versions/certificates at edge and origin, no clear-text admin services, no public SSH, and only required listeners. HSTS headers are not evidence of TLS configuration. |
| Idle session timeout, section 7.5 | Runbook recommends tmux; no enforced remote idle policy established | Open. Define and enforce an administrative idle timeout of 5 minutes or less where operationally applicable. Tailscale SSH checkPeriod is reauthentication for new connections, not an existing session idle cutoff. A detached tmux session is not an access-control boundary. |
| Restrict outbound administration, section 7.7 | APC public-copy URL validation requires public HTTPS and rejects private address destinations | Partial, not a global egress firewall or proof against every SSRF path. Inventory all fetch/provider paths, redirects and DNS resolution behavior. Block private/metadata destinations at the appropriate network boundary, preserving approved dependencies. |
| Routing and switch ports, sections 8-9 | No authoritative router/switch configuration reviewed | Open/infrastructure owned. Review forwarding, routing authentication where applicable, VLAN separation, unused ports, trunking, ARP and switch management with network owner. Do not paste Cisco IOS commands into Linux or Cloud Run. |
| Notification/consent, section 10 | No device administration banner verified | Open. Add an approved support-access notice appropriate to the organization and jurisdiction; verify it on the actual login path. |

## Priority rollout and acceptance evidence

1. Export the current tailnet policy privately. Review all grants, ACLs, SSH rules,
   group membership, tag ownership, shared devices and routes together. Narrow
   grants are additive; they cannot override an existing allow-all rule. Replace
   placeholders in the runbook with verified identities. Retain allow/deny policy
   tests for support TCP 22, denied app ports, ordinary users, terminal-to-terminal
   connections, and root/other usernames. Validate in Tailscale before rollout.
2. On a staging terminal, verify the allowed support path and a local recovery
   path before changing firewall or sudoers. Record `ss -lntup`, firewall rules,
   account/sudo permissions, OS/Tailscale versions and clock sync. Test denied
   connections from another terminal and from the customer LAN, including IPv6.
   Then roll out gradually. Do not make access changes blind on a remote device.
3. Inspect Cloud Run ingress/IAM, edge rate limits and direct `run.app` access.
   If the edge is the enforcement point, prove its controls cannot be bypassed
   through the origin; otherwise enforce equivalent controls at the origin.
   Preserve the deliberately public discovery/search API. Do not globally require
   private tailnet access or Cloud Run IAM without testing client compatibility.
4. Export device and cloud audit events to a restricted off-device destination.
   Define retention and an alert owner; test failed-login, denied privileged access,
   unexpected listener, policy-change and revoked-device alerts end to end.
5. Establish repeatable image/dependency updates and a per-device inventory.
   Test recovery and revocation: an offboarded support member and returned terminal
   must lose access. Reimage returned equipment and revoke its subscriber key.

No production policy, firewall, device, cloud service or secret was changed by
this repository update. Completion requires dated live evidence for the open items.

## Protocols in plain language

A protocol is an agreed format and sequence for computers to communicate. A
security principle is a rule about how we permit that communication. For example,
"least privilege" is a principle; "SSH" is a protocol that must be configured to
follow it.

| Term | What it does | WorkspaceAlberta use and limitation |
|---|---|---|
| TCP / UDP | Transports network traffic; TCP provides an ordered stream, UDP sends individual datagrams | A grant can permit TCP 22 without permitting all traffic. An open port alone says nothing about who may use the application. |
| TLS / HTTPS | TLS encrypts a connection and authenticates the server with a certificate; HTTPS is HTTP using TLS | Protect public API/provider requests. NSA section 7.3 calls for TLS 1.2 or higher; verify current platform settings. TLS termination may happen before the container, so internal HTTP is not automatically a public clear-text exposure. |
| WireGuard / Tailscale | WireGuard encrypts device-to-device tunnels; Tailscale manages identities, keys, connectivity and access policy around those tunnels | Private Pi management. Encryption does not imply permission to every device or port. Tailscale is not IPsec. |
| SSH | Encrypted remote shell and file-transfer transport | Use Tailscale SSH restricted to the dedicated support account. Ordinary OpenSSH over a tailnet has separate SSH authentication; Tailscale check mode does not govern that fallback. |
| OAuth / PKCE | OAuth delegates application access using tokens; PKCE binds an authorization-code exchange to the client that initiated it | Protect account and paid tools. It is not a VPN and does not encrypt traffic by itself; use HTTPS. |
| DNS / MagicDNS | Maps names to network addresses; MagicDNS provides tailnet device names | A convenient name does not grant access or prove the destination service is authorized. |
| NTP | Synchronizes clocks | Accurate time supports token expiry and event correlation. Verify sync and trusted time sources; use authenticated time where supported. |
| Syslog | Sends device event records to a logging server | One option for centralized device audit logs. Choose protected transport and restrict access; a local journal alone can disappear with a compromised or failed device. |
| IPsec / IKEv2 | IPsec protects IP traffic; IKEv2 negotiates tunnel security and keys | Relevant to traditional site-to-site VPNs and the NSA router examples. No need to add another VPN merely to copy the guide. |
| SNMPv3 | Monitors/manages network equipment with authentication and encryption when configured accordingly | Relevant if switches/routers need monitoring. Disable unused SNMP; avoid v1/v2c community-string administration. |
| RADIUS / TACACS+ / AAA | Protocols used for centralized equipment access; AAA means authentication, authorization and accounting | An architectural principle to apply through your identity provider, Tailscale policy and audit logs. Do not add a router AAA server to the app without a specific requirement. |
| VLAN / ACL / grant | VLAN separates layer-2 networks; ACLs and grants define permitted access | VLAN membership alone is not authorization. Tailnet grants do not replace customer switch/router or host firewall controls. |
| MCP | Application protocol letting AI clients discover and call tools | Runs locally over stdio or remotely over HTTP. Its presence does not provide network segmentation, encryption or permission by itself. |

## Sources

- Supplied NSA *Network Infrastructure Security Guide*, October 2023 v1.2,
  sections cited above. Kept outside Git; no attachment copy is added to the repo.
- Tailscale grants syntax: https://tailscale.com/docs/reference/syntax/grants
- Tailscale policy and test syntax: https://tailscale.com/docs/reference/syntax/policy-file
- Tailscale SSH/check mode: https://tailscale.com/docs/features/tailscale-ssh

Tailscale documentation checked 2026-10-25. This baseline adapts the guide's
principles; it does not claim NSA endorsement or CNSA algorithm compliance.

## Verification of this repository change

Documentation-only change. Existing targeted suites were run with:

```bash
python -m unittest tests.test_canadabuys_mcp_smoke tests.test_http_hardening tests.test_oauth_security tests.test_production_hardening tests.test_cloud_run_release
```

Result: 56 tests discovered, 48 passed, 8 skipped. Skips are the OAuth/Supabase
live-database tests requiring `WA_OAUTH_TEST_SUPABASE=1`; no live database tests
were enabled. Example policy JSON parses, relative documentation links resolve,
and `git diff --check` passes. Tailscale semantic validation, live connectivity,
Cloud Run configuration and device firewall checks were not performed. The
repo-local GBrain wrapper was unavailable here, so index synchronization was not run.
