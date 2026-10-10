<div align="center">

<img src="docs/assets/hero.svg" alt="🏯 SHUKI — Obsidian × Claude Code, Personal AI Intranet" width="900">

[![License: MIT](https://img.shields.io/badge/License-MIT-brightgreen.svg)](LICENSE)
[![Obsidian](https://img.shields.io/badge/Obsidian-7C3AED?logo=obsidian&logoColor=white)](https://obsidian.md/)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-D97757?logo=claude&logoColor=white)](https://claude.com/claude-code)
[![日本語](https://img.shields.io/badge/🇯🇵_日本語版-README-blue)](README.md)

</div>

> This is the English documentation for SHUKI. It lives in the **same repository** as the Japanese original — there is no separate English fork to keep in sync. To make the dashboard UI render in English, set `"lang": "en"` in `scripts/shuki_paths.json`; translations live in `scripts/i18n/en.json`, keyed by the original Japanese string, and anything missing simply falls back to the original text.

**Just talk to it, and your notes end up where they belong.**

<img src="docs/assets/demo-chat.svg" alt="Demo: a note thrown into chat gets auto-filed into knowledge notes and tasks" width="900">

## ⚡ In three lines

- 🗂 **Your whole life in local Markdown** — work, money, language learning, relationships, introspection, all in one Obsidian vault. No vendor lock-in, diffable with git.
- 🤖 **Chat is the input; files are the output** — just talk to [Claude Code](https://claude.com/claude-code). Named agents with clear roles triage, research, and file things away, while scheduled routines run unattended.
- 🚫 **What the AI is *not* allowed to do is decided upfront** — no ghostwriting, no moving money, no health calls. Guardrails are technically enforced through tool permissions.

> 🧩 **This repository publishes the core features only** — AI chat, tasks, calendar, News and decision cards. The plugins that run in the author's setup (concept codex, achievements, habits, finance, English practice, visualizations and more) are not included.

<img src="docs/assets/shuki-demo.gif" alt="Dashboard demo: task board, News, decision cards (yes/no and multiple choice), AI chat" width="900">

<sub>▲ The real dashboard (about 15 seconds), recorded from a fresh clone of this repository with only the bundled sample data. The interface language in the recording is Japanese; set `"lang": "en"` for English.</sub>

## 🗺 The big picture

<img src="docs/assets/architecture.svg" alt="Architecture: scheduler → Claude Code agents → Obsidian vault (local Markdown) → viewed in the Obsidian app" width="900">

<details>
<summary>📁 View the folder structure as text</summary>

```
Obsidian Vault (local Markdown)
├── 00_Intranet/     ← the "constitution": rules every agent must read
├── 03_Projects/     ← bundles of tasks with a deadline (type: project)
├── 04_Tasks/        ← one file per task (status / due date / assignee / area)
├── 05_Areas/        ← ongoing areas of responsibility (one hub note each)
├── 06_Resources/    ← reusable knowledge + concept nodes (the graph's hubs)
├── 01_Inbox/        ← unprocessed captures, auto-routed by the orchestrator
├── 07_Logs/         ← dated records (reviews, introspection)
└── .claude/
    ├── agents/      ← agent definitions (4 core agents; add specialized ones yourself)
    └── skills/      ← interactive, confirmation-required workflows
```

</details>

> **This repository distributes "the framework only"** — agents, rules (`00_Intranet/`), the operating manual (`CLAUDE.md`), and templates (`_Templates/`). Each PARA folder ships with a short `README.md` explaining its purpose, and **one skeletal `_example-*.md` demonstrating how to use the properties**. **It contains no personal notes, logs, or resources whatsoever** — delete the example files once you understand them.

## 🎚 How far you take it (three tiers, added one at a time)

You don't need the whole thing. **Tier A alone is a complete way to use this.** B and C are things you add once you want them, and stopping partway breaks nothing.

| Tier | What it is | What you need | Who it fits |
|---|---|---|---|
| **A. A personal wiki with an AI in it** | The vault skeleton ＋ `CLAUDE.md` ＋ `.claude/` (agents and skills) | Obsidian ＋ Claude Code | Anyone who wants to grow notes by chatting. **Start here** |
| **B. ＋ Dashboard** | Launch `scripts/dashboard_*.py` when you want it | ＋ Python 3 (standard library only — nothing to install) | People who want a kanban view of tasks, or a browser UI |
| **C. ＋ Scheduled routines** | News fetching and inbox routing, run unattended via Task Scheduler / cron | ＋ A PC that stays on (or that you open often) | People who want things to happen without them |

**If you're on Tier A, you can ignore the entire `scripts/` folder.** Cloning it changes nothing — nothing runs unless you start it (no daemons, no install step). You can add B and C later from `/setup`.

> 🔬 **For researchers**: there's a dedicated path that covers only paper tracking and task management → **[QUICKSTART-RESEARCH.md](docs/en/QUICKSTART-RESEARCH.md)** (gets you from A to B without any scheduled jobs)

## 🚀 Quick start

> Full details in [docs/SETUP.md](docs/en/SETUP.md). Here's just the essence.

**Manual work is limited to this (~15 minutes):**

1. Install [Git](https://git-scm.com/downloads) (to fetch the repo — a ZIP download works too)
2. Install [Claude Code](https://docs.claude.com/en/docs/claude-code/overview) (the star of the show; requires an Anthropic account and a paid plan)
3. Install [Obsidian](https://obsidian.md/) (a viewer for browsing notes and the graph)
4. Clone this repo (`git clone https://github.com/sflren6741/SHUKI my-vault`) → open it in Obsidian via "Open folder as vault"
5. Launch `claude` from the vault folder (`cd my-vault && claude`)

> Detailed installation steps and troubleshooting for each step are covered on a single page in [docs/SETUP.md](docs/en/SETUP.md).

**Everything else happens in chat:**

```
/setup
```

Claude Code walks you through configuring your Identity, values, Areas, path settings, Obsidian plugin guidance, and automation script generation — all interactively. You never need to edit a file directly.

Once setup is done, just talk to it ("Add a note: ...", "Show me this week's tasks in progress"). When you're stuck, **`/next`** gives you the one next action.

> The original framework is written in Japanese — see **[SHUKI](https://github.com/sflren6741/SHUKI)**. The structure and logic carry over as-is, so feel free to localize the rule files however you like.

---

## Why I built this

Work, money, English, sports, relationships, introspection — I wanted my whole life organized in one place, and on top of that, an AI layer that actually **helps run operations**, not just a chat window.

A plain chat AI forgets everything between sessions and has no opinion about "where should this piece of information live." So I turned a plain Obsidian vault into a small organization: **a set of named agents with clear roles and boundaries**, **type-driven filing**, and **scheduled routines** that run on their own. Claude Code is the runtime; Obsidian is the DB and UI.

This repository is **the framework only** — agents, rules, templates, and structure. It contains no personal notes whatsoever.

## Why I like it

- **Local-first and private** — everything is Markdown on my own machine. No vendor lock-in, fully searchable, diffable with git, editable in plain Obsidian.
- **Multiple specialists instead of one do-everything assistant** — rather than having a single assistant do everything, each agent owns a domain (triage, research, planning, knowledge) and hands off work **via tasks**, not chat that gets buried.
- **Type-driven PARA** — Projects/Areas/Resources/Archive are expressed through a `type:` property and wikilinks rather than rigid folders. Thanks to Obsidian Bases plus properties, an attribute-driven approach is vastly more flexible than a folder-driven one.
- **Trust comes from constraints** — the single most effective piece of design here is what the AI is **forbidden** from doing. No ghostwriting to sensitive recipients, no moving money, no health judgment calls — all of that stays in human territory. Several agents are read-only by tool permission, so the boundary is **technically enforced**, not just requested.
- **Compounding automation** — News fetching, inbox routing and the task dispatch run happen on a schedule (the weekly review is a skill you start yourself). QA for explicitly written rules is caught by a deterministic linter (`scripts/vault_lint.py`, no LLM) — because handing rule-checking to an LLM produces false positives.
- **A knowledge graph that grows on its own** — recurring themes become "concept nodes" linked across notes. The more you use it, the more connected the vault becomes.

## The 4 core agents (+ add your own custom ones)

| Tier | Agent | Role |
|---|---|---|
| Orchestration | `orchestrator` | Triage, weekly review, task dispatch run |
| Core | `researcher` | Concrete research for travel, purchases, comparisons (does not book or purchase anything) |
| Core | `knowledge` | Turns URLs/content into linked knowledge notes, weekly graph maintenance |
| Core | `infrastructure` | Task DB audits, duplicate/silent-failure detection (proposals only, read-only) |
| + | `<specialized agent>` | Add your own for finance, language learning, relationships, introspection, etc., to fit your life (see [AGENTS.md](docs/en/AGENTS.md)) |

**Agents = unattended and routine; skills = interactive and confirmation-required.** Sensitive work (weekly review, task audits) is run as a front-channel **skill** to make sure a human is always in the loop. There's no dedicated reviewer agent — QA is distributed across "self-QA + owner confirmation + deterministic linting."

## 📊 Dashboard (Tier B, optional)

Alongside the chat interface, a local dashboard you view in a browser ships with the repo (`scripts/dashboard_server.py` — standard library only, nothing to install). It's meant to be **started when you want it**, not left running. If you don't want it, don't start it; Tier A is complete on its own.

```
python scripts/dashboard_server.py
```

Open <http://127.0.0.1:8765/>. Copy `scripts/shuki_paths.example.json` to `shuki_paths.json` and point `vault` at your own folder (that file is gitignored).

The pages:

| Page | Contents |
|---|---|
| 🏠 Home (`/`) | Today's focus, skill launcher |
| 📋 Tasks (`/board`) | Kanban over the task DB (overdue / today / this week / in progress) |
| 📅 Calendar (`/calendar`) | Events and tasks by date (Google Calendar connection is optional) |
| 📰 News (`/news`) | Articles Claude picked from your feeds' new items (fetched with `python scripts/news_fetch.py`) |
| ⚖️ Decisions (`/decisions`) | Cards where the AI asks for a human decision |

> **Not included in this repository:** in the author's setup, a concept codex, achievements, habits, finance, English practice, visualizations and more run as plugins. This release contains the core features only, without that code. The plugin loader (`scripts/shuki_core/plugins.py`) is included.

> ⚠️ **How far the English goes today.** Fully translated: this documentation, the navigation shell, `/board` and `/news` (set `"lang": "en"` — see below). Swap the four Obsidian hub notes with [docs/en/vault-skeleton/](docs/en/vault-skeleton/). Still Japanese: the dashboard home page (`/`), the rule files under `00_Intranet/`, and the agent and skill definitions under `.claude/` — Claude Code reads those and answers you in English, so they work as-is; add `Always respond in English.` to `CLAUDE.md` to be sure. Folder names are Japanese on purpose (the scripts address them by path) — don't rename them.

## 📚 Detailed reproduction guides

The goal is **"reading this repo lets you reproduce the whole operation"** (and then customize it). Details live in [`docs/`](docs/):

| Guide                                       | Contents                                                                                     |
| ------------------------------------------- | -------------------------------------------------------------------------------------------- |
| [SETUP.md](docs/en/SETUP.md)                   | Full walkthrough: create a vault → install this repo → fill in Identity → launch Claude Code |
| [QUICKSTART-RESEARCH.md](docs/en/QUICKSTART-RESEARCH.md) | 🔬 For researchers: the shortest path to paper tracking + task management (no scheduled jobs) |
| [OBSIDIAN-SETUP.md](docs/en/OBSIDIAN-SETUP.md) | Plugins and settings (Templater / Linter / Bases / links)                                    |
| [AGENTS.md](docs/en/AGENTS.md)                 | How agents work and **how to build your own**                                                |
| [MOBILE-SYNC.md](docs/en/MOBILE-SYNC.md)       | Syncing via Android + Obsidian + **FolderSync**                                              |
| [AUTOMATION.md](docs/en/AUTOMATION.md)         | Scheduling News/routing/dispatch/deterministic QA                                            |
| [TIPS.md](docs/en/TIPS.md)                     | Mental models: type-driven PARA, **wikilinks**, concept nodes, boundaries                    |

## Day-to-day usage

The main interface is **Claude Code, not Obsidian**. Obsidian is for browsing and viewing the graph; Claude Code is for creating and organizing.

```
# Throw anything at the inbox — Claude routes it
"Add a note: I want to read 'Thinking, Fast and Slow'"
"Inbox: don't forget to follow up on the project proposal"

# Organize / search
"Show me this week's in-progress tasks"
"Summarize last week's running logs"

# Turn into knowledge
"Turn this URL into a knowledge note: https://..."
"What do I already know about <topic>?"

# Weekly review (interactive — always keeps a human in the loop)
/weekly-review
```

Everything happens in chat. Vault files are output, not input. You open Obsidian only when you want to see the graph, read a note, or get an overview via a Bases view.

## Notes

- This is a **personal system**, sharpened to fit my own thinking. Treat it as a starting point, not a finished product.
- Money, health, and outbound communication are deliberately placed behind human confirmation. I recommend keeping this guardrail.

## Contact

For questions, ideas, or configuration comparisons, **please open a [GitHub Issue](../../issues)**. It's the most reliable way to reach me.

## License

[MIT](LICENSE).
