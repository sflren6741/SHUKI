# Mobile access — reach the dashboard from your phone

> **TL;DR** — The dashboard only listens on `127.0.0.1` on the PC for security reasons (opening it to the whole LAN exposed an admin-level exec route in testing). Reach it from your phone over **Tailscale**: install Tailscale on both devices, enable **Tailscale Serve** on the PC to put an HTTPS front on port 8765, then open that HTTPS URL on your phone and optionally "Add to Home Screen" (PWA) for an app-like icon and push notifications.

The vault itself is just local Markdown files — no sync tool or viewer app is required. What you use from your phone is the **dashboard** (a browser screen), which connects to the `dashboard_server.py` process running on your PC.

---

## Why Tailscale

The dashboard listens only on `127.0.0.1:8765` on the PC. Binding it to `0.0.0.0` exposed `/exec` (an unauthenticated Claude-launch route) to anyone on the LAN in testing. For a safe cross-device connection, use Tailscale (or a similar personal VPN mesh), and restrict the PC's firewall so only Tailscale's address range (`100.64.0.0/10`) can reach port 8765.

---

## Steps

### 1. Install Tailscale on both the PC and your phone

Install from [tailscale.com](https://tailscale.com/) and sign in to the same account on both devices so they join the same tailnet.

### 2. Lock down the PC firewall (one-time, admin privileges)

Run the repo's `scripts/setup_tailscale_firewall.ps1` in an elevated PowerShell. It creates a rule that only allows inbound connections to port 8765 from Tailscale's address range.

### 3. Enable Tailscale Serve on the PC

```
tailscale serve https / http://127.0.0.1:8765
```

This forwards HTTPS traffic to the PC's Tailscale hostname into the local dashboard at `127.0.0.1:8765`. Check the hostname with `tailscale status`.

### 4. Keep the dashboard running

On the PC, as usual:

```powershell
$env:SHUKI_VAULT = (Get-Location).Path
python scripts/dashboard_server.py
```

### 5. Open it in your phone's browser

Visit `https://<your PC's Tailscale hostname>/`. The task board, calendar, news, AI chat and decision cards all work the same as on desktop.

💡 **Add to Home Screen (PWA)**: use your browser's share menu to add it to your home screen for an app-like icon. Where supported, you'll also get push notifications (Web Push).

---

## Capturing ideas on the go

- Just type what's on your mind into the dashboard's AI chat. `@orchestrator` routes it to the right place.
- To capture by voice, use the `/voice-capture` skill to save what you say straight to the inbox.
- Paste a URL from your phone's share menu into chat and the `knowledge` agent turns it into a note.

---

## Alternatives

| Approach | Notes |
|---|---|
| **Tailscale Serve** (this guide) | Free tier is enough to start. Only reachable while the PC is on |
| **Your own reverse proxy + certificate** | Works if you want to manage TLS termination yourself; more setup |
| **An always-on dashboard on a cloud VPS** | Removes the dependency on your PC being on, but means deciding to put vault data on that VPS — this repo isn't built assuming that |
