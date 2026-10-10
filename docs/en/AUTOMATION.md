# Automation — scheduled routines

> **TL;DR (EN)** — Run Claude Code headlessly on a schedule (Windows Task Scheduler / cron) to fetch the day's News, route the inbox, dispatch autonomous tasks, and run a weekly review. A small wrapper script invokes `claude -p "<prompt>"` from the vault folder. A deterministic linter (`scripts/vault_lint.py`, no LLM) does the frontmatter/status/date QA — don't hand rule-based QA to an LLM (it hallucinates violations). None of this is required to use the system by hand.

> **💡 If you use `/setup`** — the `/setup` skill auto-generates the `.ps1` wrapper scripts for you. This file is the registration procedure for Task Scheduler and a detailed reference.

Agents can be used manually (`@name`), but wiring them to a **schedule** so they "just run in the morning and at night" makes things dramatically easier.

---

## 1. How it works

Claude Code can run **headlessly (non-interactively)**. From the vault folder:

```bash
claude -p "@orchestrator Route the unprocessed files in 01_Inbox/ and fill in their properties"
```

Invoke this from your OS's scheduler (Windows: Task Scheduler; macOS/Linux: cron / launchd).
For unattended runs, pre-authorize the tools you use in `.claude/settings.json` so no permission prompt appears (see the official Claude Code docs for how to grant permissions — this varies by version, so we won't pin down fixed arguments here).

---

## 2. Recommended routines

| Routine | Frequency | Prompt / process (example) |
|---|---|---|
| News digest | Daily at 7:20 | `python scripts/news_fetch.py` (Claude picks what matters from your feeds' new items and shows it on the dashboard's `/news`; to set up feeds, see [QUICKSTART-RESEARCH.md](QUICKSTART-RESEARCH.md) §4) |
| Inbox sweep | Every few hours | `@orchestrator Route unprocessed files in 01_Inbox/ and fill in properties` (**routine, so use `--model haiku` to cut cost**) |
| Task dispatch | Daily at 12:30 | `@orchestrator Run the task dispatch run (§🚚)` (an internal delivery where AI agents advance tasks for each other, max 3 per run) |
| Vault lint (deterministic QA) | Daily at 0:05 | `python vault_lint.py --vault <VAULT>` (no LLM, outputs to `99_System/qa/`; see §4) |
| Night QA (operating summary) | **Twice a week (Wed/Sun) at 2:00** | `@infrastructure Check the run logs and update the summary` (Sunday only also runs the operational improvement scan) |
| Knowledge enrich | Weekly, Sunday at 20:00 | `@knowledge Run in maintenance mode` (wikilink upkeep, stale-content detection) |
| Weekly review | Weekly | (a human triggers the interactive `/weekly-review` skill; not generated unattended) |
| (Optional) Scheduled runs for specialized agents | As needed | `@<specialized agent> <fitting its role>` |

> Never run sensitive, confirmation-required work (like the weekly review) unattended. Trigger it as a skill, with a human at the controls (see the agent/skill division of labor in [AGENTS.md](AGENTS.md)).
>
> Night QA is limited to twice a week rather than daily so the monitoring report itself doesn't grow so large nobody reads it (a countermeasure against monitoring self-inflation).

---

## 3. Wiring it up on Windows Task Scheduler

### 3a. One-command registration (recommended)

The bundled [`scripts/register-scheduled-tasks.ps1`](../../scripts/register-scheduled-tasks.ps1) registers all of the above routines in bulk, **with retry-on-failure built in**. **Nothing runs automatically until you run this script once** (until then, you'll need to manually invoke `@orchestrator ...`), so run it first if you want automation.

1. Move the deterministic QA script outside the vault: copy `scripts/vault_lint.py` to `<WORKSPACE>\vault-scripts\`.
2. Run from **an administrator PowerShell prompt**:
   ```powershell
   & "<repo>\scripts\register-scheduled-tasks.ps1" -Vault "C:\path\to\your-vault"
   ```
3. Verify and do a test fire (don't hand everything over at once):
   ```powershell
   Get-ScheduledTask -TaskPath '\Claude\'
   Start-ScheduledTask -TaskName 'Claude-InboxSweep' -TaskPath '\Claude\'
   ```
   If the unprocessed files in `01_Inbox/` get routed and a log appears in `99_System/agent-runs/inbox_<date>.log`, it worked. To remove: `Get-ScheduledTask -TaskPath '\Claude\' | Unregister-ScheduledTask`.

Parameters and the list of registered tasks are in [`scripts/README.md`](../../scripts/README.md). Save PS1 files containing Japanese text as **UTF-8 with BOM** (to work around PowerShell 5.1 mojibake — the bundled script already handles this).

### 3b. Manual GUI registration (if you don't want to use the script)

1. Place a wrapper `.ps1` **outside** the vault. Example:
   ```powershell
   # run-inbox.ps1  — adjust paths for your environment
   Set-Location "<PATH-TO-YOUR-VAULT>"
   claude -p "@orchestrator Route the unprocessed files in 01_Inbox/ and fill in their properties" *> "<PATH-TO-LOGS>\inbox.log"
   ```
2. Task Scheduler → Create Task:
   - **Trigger**: daily at 9:00 (every few hours also works)
   - **Action**: `powershell.exe -ExecutionPolicy Bypass -File "<PATH>\run-inbox.ps1"`
   - **Conditions/Settings**: adding "restart on failure (e.g. after 30 min, up to 3 times)" makes it resilient to session limits and transient failures.

> Manage the `.ps1` files invoked by the scheduler **outside the vault** (this repo only holds agent definitions, rules, and distributable scripts). Generated run logs and QA reports (under `99_System/`) are gitignored and never committed. Copy the bundled `scripts/vault_lint.py` outside the vault before using it.

---

## 4. Deterministic QA — vault_lint.py (recommended) and optional local LLMs

**QA for explicitly written rules (frontmatter structure, `status`, `date`, dead links, etc.) should be done with deterministic code, not an LLM.** Run the bundled `scripts/vault_lint.py` (Python, PyYAML-only, designed for 0% false positives) daily, and it will output a report to `99_System/qa/YYYY-MM-DD.md`. The next morning, `orchestrator` reads it and triages what needs attention.

```bash
python scripts/vault_lint.py --vault /path/to/your-vault
```

See [`scripts/README.md`](../../scripts/README.md) for setup and schedule registration.

> ⚠️ **Lesson learned**: it's possible to try running vault QA overnight with a local LLM (Ollama, etc.), but **handing rule-based checks to an LLM produces a lot of false positives** — it's prone to "fixing" correct data by mistakenly flagging it as a violation. That's why explicit rules are pushed onto `vault_lint.py` (deterministic) instead. Local LLMs are best reserved for "preprocessing that can't be done deterministically" (OCR drafting, voice transcription, etc.).

---

## 5. Start minimal

You don't need to wire everything up at once. **Start by scheduling just the inbox sweep**, and once you feel the benefit, expand to weekly review, QA, and mobile.
</content>
