# Obsidian Setup

> **TL;DR (EN)** — Plugins and core settings that make this vault work: **Templater** (auto-inserts `created`/`date` and applies folder templates), **Obsidian Linter** (auto-updates `updated` on save), relative-path links, and an inbox-by-default new-note location. Set these once per device (`.obsidian/` is gitignored, so each device configures its own).

> **💡 If you use `/setup`** — the `/setup` skill walks you through Obsidian's configuration interactively, one step at a time. This file is the detailed reference — check it if you get stuck mid-setup.

Obsidian settings that keep this vault running smoothly. Set once and it works permanently. Listed in priority order.
`.obsidian/community-plugins.json` is included in this repo. Opening this folder as a vault in Obsidian will automatically ask "**Enable these plugins?**" Other settings (theme, panel layout, etc.) are gitignored, so **configure them per device**.

---

## 🔴 Highest priority (required for automatic dates)

### 1. Templater (community plugin)

**What it does**: automatically inserts `created` / `date` / `updated` when a note is created. Automatically applies per-folder templates.

**Install**: Settings → Community plugins → Browse → "Templater" → Install → Enable

**Configuration**:
1. Settings → Templater
2. **Template folder location**: `_Templates`
3. **Trigger Templater on new file creation**: ON
4. Add to **Folder templates**:

| Folder | Template |
|---|---|
| `04_Tasks/Task Management/Tasks` | `_Templates/Task.md` |
| `07_Logs/Logs` | `_Templates/Log.md` |
| `06_Resources/Resources/Knowledge` | `_Templates/Knowledge.md` |
| `01_Inbox/Inbox` | `_Templates/Inbox.md` |

Once configured, creating a new note in the folders above auto-fills `created` / `date`.

### 2. Obsidian Linter (community)

**What it does**: automatically updates `updated` to today's date on every save.

**Configuration**: Settings → Linter → YAML → turn on **YAML Timestamp**

| Setting | Value |
|---|---|
| Date Created Key | `created` |
| Date Modified Key | `updated` |
| Date Format | `YYYY-MM-DD` |
| Insert on file creation | ON |
| Update on file modification | ON |

---

## 🟠 Strongly recommended

### 3. Files & Links (core)

| Setting | Recommended value | Reason |
|---|---|---|
| Default location for new notes | `01_Inbox/Inbox` | Notes with no clear destination land in the inbox |
| New link format | **Relative path to file** | Won't break when the vault moves or syncs |
| Automatically update internal links | ON | Auto-updates links on rename |
| Default location for attachments | subfolder `assets` | Keeps images from scattering everywhere |

### 4. Editor (core)

| Setting | Recommended value |
|---|---|
| Default editing mode | Live Preview |
| Readable line length | ON |
| Show frontmatter | OFF (managed via the Properties UI) |
| Fold heading / Fold indent | ON |

### 5. Core plugins (enable)

Backlinks / Outgoing links / **File recovery (must be ON)** / Bookmarks / Tag pane.

### 6. Bases (core, newer Obsidian versions)

Used to build dynamic tables driven by properties like `area` / `parent` / `status`. Write the aggregate view for each Area hub and Project hub as a Bases codeblock (see this repo's `_example-*.md` files).

---

## 🟡 Nice to have

- **QuickAdd** — add a task or log with one hotkey. Set a template path + destination + filename format, and creation takes 3 seconds.
- **Recent Files** / **Another Quick Switcher** — improved navigation.
- **Theme**: Minimal / Things / AnuPpuccin, whatever you prefer.

---

## ⚙️ Vault-specific notes

- Adding `_Templates/` to Settings → Files & Links → Excluded files removes it from the graph and search (optional).
- Templater syntax (`<% tp.date.now() %>`) only expands while Templater is enabled. `_example-*.md` files use static dates, so they're readable as-is.

---

## 📋 Checklist

- [ ] Templater: installed, folder templates configured
- [ ] Obsidian Linter: YAML Timestamp configured
- [ ] Files & Links: new note → inbox / relative path / auto-update links
- [ ] File recovery → ON
- [ ] (Optional) `_Templates` added to Excluded files
</content>
