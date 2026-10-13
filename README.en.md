<div align="center">

<img src="docs/assets/hero.svg" alt="SHUKI — Claude Code personal AI intranet" width="900">

[![License: MIT](https://img.shields.io/badge/License-MIT-brightgreen.svg)](LICENSE)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-D97757?logo=claude&logoColor=white)](https://claude.com/claude-code)

[日本語](README.md)

</div>

SHUKI connects Markdown notes with AI workflows for organizing notes and tasks. Records stay in Markdown files, which Claude Code adds, searches and organizes behind the scenes. Day to day, you operate through the browser-based SHUKI dashboard — tasks, a calendar, news feeds, requests for approval, and a built-in AI chat.

<img src="docs/assets/shuki-demo.gif" alt="Dashboard demo showing the task board, news, decision cards and AI chat" width="900">

<sub>A roughly 15-second recording using the bundled sample data. The interface in the recording is Japanese.</sub>

## What's included

- A PARA folder structure, note templates and sample data — plain Markdown files, no viewer app required
- Claude Code agent definitions and workflows for setup, research and weekly reviews
- A local dashboard with AI chat, a task board, calendar, news and decision cards
- Scripts for fetching feeds, checking note structure and scheduling work

The repository contains no personal notes, logs or credentials. The author's additional plugins for finance, English practice, games and visualizations are also outside the public package.

## Getting started

Install [Claude Code](https://claude.com/claude-code), then download the repository. Claude Code requires a paid account (Claude Pro or API credits). A ZIP download works if you don't use Git.

```sh
git clone https://github.com/sflren6741/SHUKI my-vault
cd my-vault
claude
```

Run `/setup` in Claude Code to configure your profile, areas of responsibility and local paths.

See the [setup guide](docs/en/SETUP.md) for installation and configuration details. For paper tracking and task management, use the [research quick start](docs/en/QUICKSTART-RESEARCH.md).

### Running the dashboard (this is where day-to-day use happens)

Use Python 3.11 or newer. Set `SHUKI_VAULT` to the absolute path of your vault and start the server from the repository root. In PowerShell:

```powershell
$env:SHUKI_VAULT = (Get-Location).Path
python scripts/dashboard_server.py
```

Open <http://127.0.0.1:8765/> in your browser. Starting it needs PyYAML (`pip install pyyaml`); the rest of the core runs on the Python standard library. AI chat needs the selected CLI configured; Google Calendar integration needs additional packages and an account connection. See [scripts/README.md](scripts/README.md) for details.

The dashboard calls Claude Code behind the scenes, so a Claude Code account is required, but everyday use happens entirely through the dashboard's screens. Scheduled jobs are optional — see the [automation guide](docs/en/AUTOMATION.md) if you want them.

## Everyday use

Tell Claude Code what you want to save or organize.

```text
Add a note: I want to read 'Thinking, Fast and Slow'
Show me this week's in-progress tasks
Turn this URL into a knowledge note: https://...
```

<img src="docs/assets/demo-chat.svg" alt="Illustrated chat example showing a note being saved and a task search" width="900">

<sub>An SVG illustration of chat interactions, shown in Japanese.</sub>

You can see the resulting notes on the dashboard's task board and calendar. They also stay on disk as files, so you can open and edit them in any editor. Wikilinks connect related notes; properties hold task status, due dates and other metadata. Use `/next` to choose a task to work on and `/weekly-review` for an interactive review.

| Dashboard page | Use |
|---|---|
| Home and Tasks (`/` and `/board`) | Check task status, due dates and assignees |
| Calendar (`/calendar`) | View events and tasks by date |
| News (`/news`) | Read articles selected from subscribed feeds |
| Decisions (`/decisions`) | Answer requests for approval or information |

## How it works

<img src="docs/assets/architecture.svg" alt="Architecture showing chat and a scheduler using Claude Code to read and write a Markdown vault, which the SHUKI dashboard also operates on" width="900">

<sub>The relationship between chat, agents and notes. Scheduled jobs shown in the diagram require separate configuration.</sub>

Agent roles live in `.claude/agents/`, interactive workflows in `.claude/skills/`, and shared rules in `00_Intranet/`. These files are the places to adapt the system to your own use.

| Agent | Responsibility |
|---|---|
| `orchestrator` | Route inbox items, hand off tasks and coordinate reviews |
| `researcher` | Research and compare options; does not book or purchase |
| `knowledge` | Turn external content into notes and link related material |
| `infrastructure` | Check the task database for duplicates and operational problems; proposes changes |

The [agent guide](docs/en/AGENTS.md) explains how to add your own.

<details>
<summary>Folder structure</summary>

```text
my-vault/
├── 00_Intranet/     Shared rules
├── 01_Inbox/        Unsorted notes
├── 02_Home/         Home
├── 03_Projects/     Projects with deadlines
├── 04_Tasks/        One file per task
├── 05_Areas/        Ongoing areas of responsibility
├── 06_Resources/    Knowledge and concept notes
├── 07_Logs/         Dated records
├── _Templates/     Note templates
├── .claude/        Agent and workflow definitions
└── scripts/        Dashboard and maintenance scripts
```

The folder READMEs and `_example-*.md` files show where records go and how their properties work.

</details>

## Why I built it, and its boundaries

I built SHUKI to keep work tasks, reading notes and things I wanted to think through in one place, with AI helping me organize them. Records stay as files I can search and edit after a conversation ends.

Notes are stored locally. Content included in a cloud AI prompt is sent to that provider.

Payments, health decisions and outbound communication require human approval. Each agent has a defined scope and tool permissions. This is a personal system; review the rules and settings when adapting it to your own use.

<a id="english-ui"></a>

## Language

Choose English under **Settings → Display language** in the dashboard. Labels without a translation stay in Japanese. Your note contents are not translated.

English guides are in [docs/en/](docs/en/), with optional English hub notes in [docs/en/vault-skeleton/](docs/en/vault-skeleton/). Some rules and agent definitions remain in Japanese. To request English replies from Claude Code, add `Always respond in English.` to `CLAUDE.md`. Scripts refer to some folder names directly, so check those references before renaming folders.

## Guides

| Guide | Contents |
|---|---|
| [Setup](docs/en/SETUP.md) | Installation and initial configuration |
| [Research quick start](docs/en/QUICKSTART-RESEARCH.md) | Paper tracking and task management |
| [Agents](docs/en/AGENTS.md) | Defining roles and adding agents |
| [Mobile sync](docs/en/MOBILE-SYNC.md) | Reaching the dashboard while you're out |
| [Automation](docs/en/AUTOMATION.md) | Configuring scheduled jobs |
| [Design notes](docs/en/TIPS.md) | PARA, wikilinks, concept notes and agent scope |

## Contact and license

Questions and bug reports are welcome in [GitHub Issues](https://github.com/sflren6741/SHUKI/issues).

[MIT License](LICENSE).
