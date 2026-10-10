# Setup — reproduce this system

> **TL;DR** — Install three tools (Git, Claude Code, Obsidian), download this repo, then launch `claude` in a terminal and type `/setup`. Everything else gets configured through chat. You never need to edit a file directly.
>
> **Rough time estimate**: about 10–15 minutes of manual work + about 10–15 minutes of interactive `/setup` conversation.

This page is written so it's self-contained — each step includes a light explanation of "what this is actually doing." If you get stuck, read the 💡 note in that section.

---

## 0. Three prerequisites, in short

- **Claude Code** … the "brain" of this system. An AI that runs in a terminal (a black screen) and does all the file creation, organizing, and automation. **Your main interface.**
- **Obsidian** … a "viewer/DB" for Markdown files. Used for the graph view, tables (Bases), and reading notes. Not the primary tool for editing.
- **Git** … a tool for downloading this repo (template). You'll only use it once.

> In short: "write and organize with Claude Code → browse with Obsidian."

---

## 1. Prerequisites (manual, human work — ~15 min)

**This is the only manual part.** Install four tools, place the repo, and get as far as launching `claude`.

### ① Install Git (to fetch the repo)

Used to `git clone` this repo. A ZIP download also works (see the alternative in step ④).

| OS | How to install |
|---|---|
| Windows | Run the installer from <https://git-scm.com/download/win> (clicking "Next" through everything is fine) |
| Mac | Running `git --version` in Terminal will prompt you to install it if missing. Or use <https://git-scm.com/download/mac> |
| Linux | `sudo apt install git` (Debian/Ubuntu), etc. |

💡 **What a "terminal" is**: the black screen where you type commands. On Windows it's "PowerShell" or "Terminal," on Mac it's "Terminal.app." Search for it in the Start menu / Spotlight.

### ② Install Claude Code (the AI itself)

Official instructions: <https://docs.claude.com/en/docs/claude-code/overview>

- Either the **CLI version** (type `claude` in a terminal) or the **VS Code extension** works. If unsure, start with the CLI.
- Running it requires a **paid Anthropic account** (no free tier).
  - Either Claude Pro ($20/month and up) or API credits.
  - Sign up at: <https://claude.ai/> (Pro) / <https://console.anthropic.com/> (API)

💡 After installing, if `claude --version` shows something in the terminal, it worked.

### ③ Install Obsidian (the viewer)

Official site: **<https://obsidian.md/>** → download the build for your OS from "Get Obsidian / Download" and run it.

- Windows: run the `.exe` → click through to finish
- Mac: open the `.dmg` and drag Obsidian into Applications
- Free for personal use. No account required.

💡 A "vault" is the term for "one folder full of notes" managed by Obsidian. The folder you create in step ④ becomes that vault.

### ④ Download this repo (place the template locally)

In a terminal, navigate to wherever you want to keep your notes, then run:

```bash
git clone https://github.com/sflren6741/SHUKI my-vault
```

This creates a folder called `my-vault` containing the whole template. You can rename `my-vault` to whatever you like.

💡 **If you don't want to use Git**: click the green "Code" button on the GitHub page → "Download ZIP," extract it wherever you like, and use that folder as `my-vault` (the rest of the steps are the same).

🔒 **If you were invited to the repository while it's still private**: the `git clone` above won't work as-is — you'll get `Repository not found`. Take either route:

- **Get it as a ZIP (easiest, recommended)** — log into GitHub, open the repository page, then "Code" → "Download ZIP". No authentication setup required.
- **Use `git clone`** — this needs authentication. The smoothest option is to install the [GitHub CLI](https://cli.github.com/) and run `gh auth login` once; after that the `git clone` above works unchanged. Without the CLI, create a token under GitHub Settings → Developer settings → **Personal access tokens** and paste it into the password prompt when cloning (your account password won't work).

Either way, **accept the invitation first** via the link in the invitation email.

### ⑤ Open it in Obsidian as a vault

1. Launch Obsidian
2. Choose "**Open folder as vault**"
   - Either on the first-launch screen, or via the vault-switcher icon in the bottom-left → "Open folder as another vault"
3. Select the `my-vault` folder you created in ④
4. If asked "Trust author and enable plugins?" choose **Trust** (to use the bundled plugins)

💡 Right after opening, you may be asked "Enable community plugins?" `/setup` will walk you through this, so it's fine to enable them now for a smoother flow (you can also do it later).

### ⑥ Launch `claude` from the vault folder

In a terminal, navigate to the vault folder and start Claude Code:

```bash
cd my-vault
claude
```

💡 `cd` means "change directory." `cd my-vault` moves you into that folder, and `claude` launches the AI. If using the VS Code extension, open the `my-vault` folder in VS Code and launch it from the extensions panel instead.

> **If integrating into an existing vault**: just copy `.claude/` `00_Intranet/` `CLAUDE.md` `_Templates/` `scripts/` into your own vault.

---

## 2. Let `/setup` finish the rest

Once `claude` is running, just type this in the chat box:

```
/setup
```

From there, Claude Code will **ask you questions** (1–2 at a time) and configure all of the following. **You never need to edit a file by hand.**

| What gets configured | What it does | Your part |
|---|---|---|
| Identity.md (profile, boundaries) | Fills in name, occupation, areas off-limits to AI, etc. | Just answer the questions |
| Philosophy & Values.md (values, principles) | Defines the values you care about | Just answer the questions |
| Areas (life-area hubs) | Auto-creates area files like "Work," "Health," etc. | Just name the areas |
| Path settings in CLAUDE.md | Auto-replaces `<WORKSPACE>` etc. with real paths | Just answer with your paths |
| Obsidian plugin configuration | Walks you through Templater/Linter etc. step by step | GUI clicks on your end (see below) |
| Automation scripts (optional) | Generates `.ps1` files for morning/night runs | Just say yes or no |
| Specialized agents (optional) | Adds your own AI for finance, language learning, etc. | Just describe the role |

> ⚠️ **Only the Obsidian plugin setup requires GUI interaction** (Claude can't click the screen directly). But it guides you step by step ("Settings → ◯◯ → turn on △△"), so you won't need to go searching. For more detail, see [OBSIDIAN-SETUP.md](OBSIDIAN-SETUP.md).

💡 You don't have to do everything at once. **Skipping automation (optional)** is fine — the system still works normally. It's best to just fill in Identity and Areas first, start using it, and expand once you're comfortable.

---

## 3. What you can do after setup

**Start by just talking to it.** Say "Add a note: ..." and it lands in the inbox; "Make it a task" turns it into a task. When you're stuck, `/next` gives you the one next action.

The main interface remains **Claude Code (chat)** throughout. Think of Obsidian as view-only.

```
# Throw anything at the inbox (Claude figures out where it goes)
"Create a task: research 〇〇"
"Note: I want to read △△"

# Turn into knowledge (give it a URL, it makes a note and links it)
"Turn this URL into a knowledge note: https://..."

# Check status
"Show me this week's in-progress tasks"

# Weekly review (interactive — always keeps a human in the loop)
/weekly-review
```

💡 If you get stuck, run `/setup` again and it'll show you an "what would you like to update?" menu (re-running it puts it into update mode).

---

## 4. Common issues

| Symptom | Fix |
|---|---|
| `claude` says "command not found" | Step ② isn't finished. Restart the terminal and check `claude --version` |
| `git` not found | Step ① isn't installed. Or download the ZIP instead (step ④) |
| `git clone` fails with `Repository not found` | The repository is private and you were invited to it. Accept the invitation, then use the 🔒 route in step ④ (ZIP, or `gh auth login`) |
| Dates aren't auto-filling in Obsidian notes | Plugins aren't configured yet. Use `/setup`'s plugin guide, or run through [OBSIDIAN-SETUP.md](OBSIDIAN-SETUP.md) |
| Not sure if it's safe to enable a plugin | This repo is framework-only, with no personal data. Safe to Trust |
| Garbled text / hard to read Japanese | The framework is written in Japanese by default. Feel free to translate/localize the rule files |

---

## Reference docs (read as needed)

| Doc | When to read it |
|---|---|
| [OBSIDIAN-SETUP.md](OBSIDIAN-SETUP.md) | When you want to configure plugins manually in detail |
| [AGENTS.md](AGENTS.md) | When you want to understand how agents work and how to build your own |
| [AUTOMATION.md](AUTOMATION.md) | When you want to set up morning/night automation (Task Scheduler registration, etc.) |
| [TIPS.md](TIPS.md) | When you want to understand type-driven PARA, wikilinks, and concept nodes |
| [MOBILE-SYNC.md](MOBILE-SYNC.md) | When you want to sync with your phone (Android) |

> This repo isn't "the right answer" — it's a **starting point**. The more you grow it to fit your own thinking, the better it works.
</content>
