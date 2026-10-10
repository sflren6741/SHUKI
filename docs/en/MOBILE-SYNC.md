# Mobile sync — Android + Obsidian + FolderSync

> **TL;DR (EN)** — Your vault lives in a cloud folder (e.g. Google Drive) on desktop. On Android, **FolderSync** mirrors that cloud folder to a *local* folder, and the Obsidian Android app opens the local folder as a vault. Use two-way sync, sync before and after you edit, and you can capture/read anywhere. This is one known-good recipe — swap the cloud backend or sync tool to taste.

On the PC side, keep the vault in a cloud-synced folder (e.g. Google Drive). On Android, **FolderSync** mirrors that cloud folder to a **local folder**, and Obsidian Android opens that local folder as a vault. This lets you capture and browse while out and about.

> ⚠️ This is "one recipe that works." Feel free to swap the cloud backend (Google Drive / Dropbox / OneDrive...) or sync tool (FolderSync / Syncthing / Obsidian Sync / git) to your taste. The one thing that's constant is that Obsidian Android **can only open a local folder as a vault**, so you need some kind of cloud-to-local mirror.

---

## The shape

```
[PC]  vault = a cloud-synced folder (under Google Drive for Desktop, etc.)
                     ⇅ cloud (Google Drive)
[Android]  FolderSync: cloud folder ⇄ local device folder
                     ↓
           Obsidian Android: opens the local folder as a vault
```

---

## Steps

### 1. PC side
- Put the vault inside a cloud-synced folder (e.g. under Google Drive for Desktop's My Drive).
- Confirm the vault folder has synced up to the cloud.

### 2. Android — FolderSync
1. Install **FolderSync** (free) or FolderSync Pro from the Play Store.
2. **Accounts** → add and authenticate your cloud provider (Google Drive, etc.).
3. **Folderpairs** → create new:
   - **Sync type**: two-way
   - **Remote folder**: the vault folder in the cloud
   - **Local folder**: any folder on the device (e.g. `/storage/emulated/0/Obsidian/MyVault`)
   - **Sync options**: enable "Sync on schedule" (e.g. every 15–30 min) + "Sync when files change"
   - **Conflict rule**: your preference, e.g. "Use most recent file" (see the caution below too)
4. Run a manual sync once and confirm the vault lands locally.

### 3. Android — Obsidian
1. Install Obsidian Android.
2. **Open folder as vault** → select FolderSync's **local folder**.
3. Set up plugins (Templater, etc.) per device (it's safest to exclude `.obsidian/` from syncing — see below).

---

## Avoiding conflicts

The biggest enemy of two-way sync is **conflicts from simultaneous editing**. Practical tips:

- Get in the habit of syncing manually **once before editing and once after** (especially when moving between PC and phone).
- Don't leave one device open while editing on the other.
- Enabling FolderSync's **instant sync (change-triggered sync)** reduces conflicts.
- It's safe to **exclude** `.obsidian/` (Obsidian settings/cache) and `.git/` from syncing. In FolderSync's Folderpair → Filters, exclude `.obsidian` / `.git` / `.trash`. Assume these are per-device settings (this repo also gitignores `.obsidian/`).
- Commit important changes to git beforehand, so you can roll back in the worst case.

---

## Capturing on the go

- Just drop a new note into `01_Inbox/Inbox/` whenever an idea strikes. Once you're back at your PC, `@orchestrator` routes it.
- Placing Obsidian's "new note" widget/shortcut on your Android home screen makes capturing instant.
- Sharing a URL to `01_Inbox` from the share menu is also handy (add `type: 🔗URL` and the knowledge agent will turn it into a knowledge note).

---

## Alternatives

| Method | Notes |
|---|---|
| **Obsidian Sync** (official, paid) | Smartest conflict resolution. Settings sync too. Trading money for convenience |
| **Syncthing** | P2P, no cloud middleman. Privacy-focused |
| **git** (manual push/pull) | Keeps history, but fiddly to operate on mobile |
| **FolderSync** (this guide) | Cloud-based, free to start, keeps a real local copy on the device |
</content>
