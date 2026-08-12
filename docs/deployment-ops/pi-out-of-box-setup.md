# Raspberry Pi Out-of-Box Setup

A complete beginner's guide to setting up a WorkspaceAlberta CEO productivity terminal from a sealed box. No prior Raspberry Pi experience required.

By the end of this guide you will have a working AI-assisted productivity desk: ChatGPT Desktop for conversational AI, Codex CLI for terminal-based coding help, OpenCode for MCP agent workflows, and Tailscale for remote support without router hassles.

---

## 1. What You Need

Before you start, gather these items:

| Item | Notes |
|------|-------|
| **Raspberry Pi 5 16GB** | The 16GB RAM model. Smaller models will work but may run slower with heavy AI workloads. |
| **Power supply** | The official Raspberry Pi 45W USB-C power supply (white). Using an underpowered supply causes throttling and crashes. |
| **Storage** | A high-quality microSD card (32GB minimum, 64GB+ recommended) or an NVMe SSD with a Pi 5-compatible HAT. |
| **Display** | Any monitor with HDMI input. The full terminal spec uses dual 4K monitors, but a single display works fine for initial setup. |
| **Micro-HDMI to HDMI cable** | The Pi 5 uses micro-HDMI ports, not full-size HDMI. |
| **Keyboard and mouse** | USB or Bluetooth. Any keyboard and mouse will work for setup. |
| **Ethernet cable** (recommended) | Wired internet is more reliable during setup. Wi-Fi works but adds troubleshooting steps if it fails. |

For the full premium terminal hardware list (dual monitors, Ergotron arm, aluminum plinth), see [`../terminal-spec.md`](../terminal-spec.md).

---

## 2. Flash the Operating System

The operating system is the software that runs the Pi. You need to write it to your storage card before the Pi can boot.

### Recommended OS

**Ubuntu Desktop 24.04 LTS ARM64** — This is the primary recommendation. Ubuntu 24.04 is officially validated for the ChatGPT/Codex Linux desktop app and provides a smooth, modern desktop experience.

**Alternate:** Raspberry Pi OS Bookworm Desktop (64-bit) also works and boots quickly. The ChatGPT desktop app may show warnings on older OS versions.

### Step-by-step

1. **Download Raspberry Pi Imager** on your main computer (Windows, Mac, or Linux):
   - [https://www.raspberrypi.com/software/](https://www.raspberrypi.com/software/)
   - Install and open it.

2. **Insert your storage** (microSD card or NVMe SSD via USB adapter) into your main computer.

3. **In Raspberry Pi Imager:**
   - Click **Choose Device** → select **Raspberry Pi 5**.
   - Click **Choose OS** → scroll to **Other general-purpose OS** → **Ubuntu** → **Ubuntu Desktop 24.04 LTS (64-bit)**.
   - Click **Choose Storage** → select your microSD or SSD.

4. **Click Next.** A dialog asks if you want to apply customization.

5. **Click Edit Settings** (recommended):
   - **Hostname:** Enter a name like `wa-pi5-yourname-01` (lowercase, no spaces).
   - **Username and password:** Create your admin account. Remember this password — you will need it for `sudo` commands.
   - **Wireless LAN:** If you are using Wi-Fi, enter your network name and password here.
   - **Locale settings:** Set your timezone (e.g., `America/Edmonton` for Alberta).
   - **Services tab (optional):** Enable SSH if you want remote terminal access before Tailscale is set up.

6. **Click Save**, then **Yes** to apply settings.

7. **Wait for the write and verification** to complete. This takes 10–30 minutes depending on your card speed.

8. **Remove the card/SSD** from your computer when finished.

---

## 3. First Boot

1. **Insert the storage** into your Raspberry Pi 5:
   - MicroSD: slot on the underside of the board.
   - NVMe: mounted on a HAT above or below the board (follow your HAT instructions).

2. **Connect the display** using the micro-HDMI cable.

3. **Connect keyboard and mouse.**

4. **Connect Ethernet** (recommended) or ensure Wi-Fi credentials were set during imaging.

5. **Plug in the power supply.** The Pi will boot automatically.

6. **Wait for Ubuntu (or Raspberry Pi OS) to start.** First boot takes longer as the system expands to fill the card and runs initial setup.

7. **Follow the on-screen setup wizard:**
   - Select language and keyboard layout.
   - Connect to Wi-Fi if you did not set it during imaging.
   - Set your timezone if prompted (e.g., **Canada/Edmonton** for Alberta).
   - Create your admin user if you skipped it during imaging.
   - Skip or defer online accounts — you do not need Ubuntu One for this.

8. **Let the system finish any background updates** before proceeding. You may see a "Software Updater" prompt.

---

## 4. Run System Updates

Open a terminal. On Ubuntu Desktop, press `Ctrl+Alt+T` or search for "Terminal" in the applications menu.

Run:

```bash
sudo apt update && sudo apt full-upgrade -y
```

**What this does:** Downloads the latest package lists (`update`) and installs all available upgrades (`full-upgrade`). This ensures your system is current before installing additional software.

**Note:** The CEO installer script will also run updates, so this step is optional if you prefer to let the installer handle it.

If prompted, enter the password you created during setup. You will not see characters as you type — this is normal.

---

## 5. Run the CEO Software Installer

The installer script sets up the AI productivity tools: Tailscale, Codex CLI, ChatGPT Desktop, and OpenCode.

### Basic install

```bash
git clone https://github.com/HarleyCoops/WorkspaceAlberta.git ~/WorkspaceAlberta
cd ~/WorkspaceAlberta
chmod +x installer/install-ceo-pi.sh
./installer/install-ceo-pi.sh
```

**What this does:**

1. **git clone** downloads the WorkspaceAlberta repository to your home folder.
2. **cd** changes into that folder.
3. **chmod +x** makes the installer script executable.
4. **./installer/install-ceo-pi.sh** runs the installer.

The installer will prompt for your `sudo` password. Let it run to completion — it installs packages, configures services, and downloads the AI desktop apps.

### With Tailscale auto-join (optional)

If your IT administrator gave you a Tailscale auth key and hostname, you can join the support network automatically:

```bash
export HOSTNAME_FQ="wa-pi5-yourcompany-edmonton-01"
export TS_AUTHKEY="tskey-auth-..."
./installer/install-ceo-pi.sh
```

**What is Tailscale?** Tailscale is a private VPN that lets support staff reach your terminal remotely without opening router ports or exposing your Pi to the public internet. If something goes wrong, your support team can connect securely to troubleshoot.

For the full list of installer options, see [`ceo-pi-setup.md`](ceo-pi-setup.md).

---

## 6. First-Login Checklist

After the installer finishes, open a **new terminal** (or run `source ~/.bashrc`) so the new tools are on your PATH.

### 1. Sign into ChatGPT Desktop

- Open the applications menu and launch **ChatGPT**.
- Sign in with your OpenAI account (create one at [chat.openai.com](https://chat.openai.com) if needed).
- Once signed in, you can use ChatGPT directly on your desktop.

### 2. Authenticate Codex CLI

In the terminal, run:

```bash
codex
```

A browser window will open. Sign in with your OpenAI account. Once authenticated, Codex CLI can help you write and debug code from the terminal.

### 3. Authenticate OpenCode

In the terminal, run:

```bash
opencode
```

Follow the authentication prompts for your preferred AI provider. OpenCode connects to the WorkspaceAlberta MCP agents for procurement and other workflows.

### 4. Approve Tailscale (if no auth key was provided)

If you ran the installer without a `TS_AUTHKEY`, Tailscale is installed but not connected. To join:

```bash
sudo tailscale up --advertise-tags="tag:wa-terminal,tag:wa-pi5" --ssh
```

This prints a URL. Open it in a browser, sign in to your organization's Tailscale account, and approve the device. Ask your IT administrator if you do not have a Tailscale account.

### 5. Install Python dependencies for procurement tools

```bash
cd ~/WorkspaceAlberta
python3 -m pip install -r requirements.txt
```

This installs the Python packages needed for the CanadaBuys MCP server and procurement tools.

---

## 7. You're Done When...

Run these checks to confirm everything is working:

```bash
# Check hostname
hostname

# Check Tailscale connection
tailscale status
tailscale ip -4

# Check AI tools
codex --version
opencode --version
dpkg -l | grep chatgpt

# Run the procurement MCP smoke test
cd ~/WorkspaceAlberta
python3 -m unittest tests.test_canadabuys_mcp_smoke
```

**Expected results:**

- `hostname` shows your device name.
- `tailscale status` shows "Connected" or lists your Tailscale IP.
- `codex --version` and `opencode --version` print version numbers.
- `dpkg -l | grep chatgpt` shows a line with "chatgpt" (the desktop app).
- The smoke test prints "OK" without errors.

If all checks pass, your CEO productivity terminal is ready to use.

---

## 8. If Something Goes Wrong

### "command not found" after installing Codex or OpenCode

The tools are installed, but your terminal does not see them yet. Fix:

```bash
source ~/.bashrc
```

Or close and reopen the terminal window. The installers add paths to `~/.bashrc`, which loads when you open a new terminal.

### "permission denied" running the installer

You forgot to make the script executable. Fix:

```bash
chmod +x installer/install-ceo-pi.sh
./installer/install-ceo-pi.sh
```

### "sudo: incorrect password" or "user is not in the sudoers file"

You either typed the wrong password or your user does not have administrator access. Fixes:

- Double-check you are typing the password you created during first boot.
- If you did not create a user during imaging, you may be logged in as a default user without sudo. Re-flash the card with proper user settings in Raspberry Pi Imager.

### No network connection

Check physical connections first:

1. Is the Ethernet cable plugged in at both ends? Try a different cable.
2. For Wi-Fi, is the network name and password correct? Open Settings → Wi-Fi and reconnect.
3. Can you reach the router? Run `ping 8.8.8.8` — if it works, DNS may be the issue. Try `ping google.com`.

If Ethernet works but Wi-Fi does not, use Ethernet for setup and troubleshoot Wi-Fi later.

### Tailscale not joining or "failed to connect"

1. Confirm internet connectivity first (`ping 8.8.8.8`).
2. Check if Tailscale is running:

   ```bash
   sudo systemctl status tailscaled
   ```

3. If stopped, start it:

   ```bash
   sudo systemctl start tailscaled
   ```

4. Try joining again:

   ```bash
   sudo tailscale up --advertise-tags="tag:wa-terminal,tag:wa-pi5" --ssh
   ```

5. If you have an auth key but it is expired or invalid, ask your administrator for a fresh key.

### ChatGPT Desktop does not start or shows errors

The desktop app is validated for Ubuntu 24.04/26.04 and Fedora. On Raspberry Pi OS Bookworm it may show compatibility warnings.

- Try running it from the terminal to see error messages:

  ```bash
  chatgpt
  ```

- If it fails due to missing libraries, ensure your system is fully updated:

  ```bash
  sudo apt update && sudo apt full-upgrade -y
  ```

### Smoke test fails

If `python3 -m unittest tests.test_canadabuys_mcp_smoke` fails:

1. Confirm you installed dependencies:

   ```bash
   cd ~/WorkspaceAlberta
   python3 -m pip install -r requirements.txt
   ```

2. Check for import errors in the output — they usually indicate a missing package.

3. Run the MCP server directly to see detailed errors:

   ```bash
   python3 mcp-servers/canadabuys/server.py
   ```

---

## Next Steps

- Read the full software installer reference: [`ceo-pi-setup.md`](ceo-pi-setup.md)
- Learn about remote support: [`tailscale-pi-remote-support.md`](tailscale-pi-remote-support.md)
- Explore the terminal hardware spec: [`../terminal-spec.md`](../terminal-spec.md)
- Set up Codex and OpenCode configuration: [`../codex-setup.md`](../codex-setup.md)
