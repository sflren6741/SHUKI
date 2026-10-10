# Claude work space — AI Intranet

> 📖 **New here?** Start with the [README](README.md) (overview, philosophy, setup).
> This file is the **operating manual body** that Claude Code loads every session, and it's written for the owner's personal vault. Placeholders like `<...>` and `<WORKSPACE>` should be replaced with your own environment's values. The fastest way to bootstrap is `/setup`.

This is the owner's AI agent operating intranet. A local vault with a PARA structure. Also editable in Obsidian.

## 🗂 Directory map

| Path | Role |
|---|---|
| `03_Projects/` | Project hub (`Projects.md` is the hub, each Project `.md` lives under `Projects/`) |
| `00_Intranet/` | Constitution / operating rule set (the index the AI always consults) |
| `00_Intranet/README.md` | Entry guide for the AI, quick-reference by role |
| `00_Intranet/📖 How to Use the Vault.md` | **For humans** — one-page usage summary (skill quick-reference, directory quick-reference, list of automated processes) |
| `00_Intranet/AI Operating Rules (Intranet)/` | Individual rules (Identity / Philosophy & Values / Design Language / QA Cycle / Stop Rule / Work Discipline, etc.) |
| `99_System/` | **Machine zone (humans don't normally need to open this)**. Working area for AI and scripts. Contents are private — information for humans arrives via `/ops-review` |
| `99_System/agent-runs/` | Agent execution logs. **Consolidated into `.log` files**: the historical record lives in daily `<track>_YYYY-MM-DD.log` files (one file per day, full text). "Check the history" means opening that day's `.log` |
| `99_System/monitoring/` | Operating summaries and operational improvement proposals |
| `99_System/qa/` | Storage for `vault_lint.py`'s daily QA reports (organized by date, triaged by the morning orchestrator) |
| `04_Tasks/Task Management.md` | Task management hub (inline base DB) |
| `04_Tasks/Task Management/Tasks/` | Task DB (each `.md` is one task) |
| `02_Home/` | Home / today's focus |
| `05_Areas/` | Ongoing areas of responsibility (`Areas.md` is the hub; each Area is a single hub file `<area>.md` only, no folders) |
| `06_Resources/` | Knowledge (`Resources.md` hub + inline base DB) |
| `06_Resources/Resources/Knowledge/` | Knowledge DB body (books, articles, etc. — each `.md` is one entry). **👤 person notes also live here** (`type: 👤Person`) |
| `06_Resources/Resources/Concepts/` | Concept nodes (recurring themes, principles, insights — the graph's semantic hubs) |
| `01_Inbox/` | Unprocessed items (`Inbox.md` hub + inline base DB) |
| `08_Archive/` | Archive |
| `07_Logs/` | Activity log (`Logs.md` hub + inline base DB, entries live in the `Logs/` subfolder) |
| `.claude/agents/` | Claude Code subagent definitions (**the sole source of truth**; 4 core agents + optional specialized agents) |
| `.claude/skills/` | Manual, interactive skills (invoked with `/` commands) |
| `scripts/` | Bundled scripts (`vault_lint.py`, etc. — see `scripts/README.md` for details) |

## 🤖 Available agents

Invoke with `@<agent-name>` or the Agent tool:

> ⚠️ **This list is a summary (for navigation).** The authoritative spec, triggers, and constraints for each agent live in **`.claude/agents/<agent-name>.md` — that file is the sole source of truth**. If this list, the org chart, or the README ever disagree with `.claude/agents/`, trust `.claude/agents/`. Editing this list does not change an agent's behavior (to change behavior, edit `.claude/agents/`).

> 🔀 **Agent vs. skill division of labor**: agents = unattended, can run on a schedule. Skills = manual, interactive (invoked by the owner).

### Core (required, 4 agents)
- **`@orchestrator`** — Task triage, weekly review, task dispatch run (§🚚)
- **`@researcher`** — Executes concrete research using WebFetch (comparison tables, travel planning, purchase analysis). Does not carry out actual bookings or purchases
- **`@knowledge`** — Converts URLs/external content into knowledge notes, builds wikilinks, weekly maintenance
- **`@infrastructure`** — Task DB audits (detects items **stalled 7+ days**), duplicate detection, silent-failure monitoring, operational improvement scans (detection/proposal only — read-only on the vault body, may only update monitoring aggregates)

### Specialized agents (optional additions)

Add to `.claude/agents/` to fit your own use cases. See `docs/en/AGENTS.md` for how to build one, and `📋 Common Agent Template.md` for the format.

Examples: household finance / language learning / relationship support (memory organization, fact-checking — no ghostwriting) / introspection (cross-log pattern extraction).

### Skills (manual, interactive) — invoked with `/` commands

You don't have to memorize these — **just talking normally is usually fastest** ("build my schedule," "I'm stuck"), and the dashboard's home page lists them as buttons. Installed skills:

- **`/next`** — The one next action (when you're stuck and can't move, it gives you exactly one "thing to do right now" with a reason)
- **`/research <topic>`** — Literature search across OpenAlex + arXiv + web, returning related work, open gaps, a taxonomy, and a relationship diagram
- **`/schedule`** — Assigns tasks and appointments into open time blocks
- **`/check-in`** — A lightweight self-check-in (5-minute pulse check / log analysis)
- **`/audit-tasks`** — Task DB audit (interactive)
- **`/discuss`** — Thinking out loud about ideas (doesn't push toward a conclusion)
- **`/plan`** — Structuring strategy/goals (milestone breakdown → create a Project + break into tasks)
- **`/scan`** — Interactive refinement of vault files
- **`/weekly-review`** — Weekly review (interactive)
- **`/ops-review`** — Review and improve vault operations through conversation
- **`/setup`** — Initial setup / profile and Areas configuration

## 🧠 Local AI (Ollama, etc.) — an optional auxiliary layer

You can optionally add a separate layer to support the vault (managed under `<LOCAL_AI_DIR>\`). Good for "heavy preprocessing done outside the vault, then dropped into the inbox" use cases like OCR drafting or voice transcription.

**Boundaries** (principles if you add one):
- ✅ Output is limited to drafts (e.g. `_ocr_out/`) or inbox submissions
- ❌ Never edits or deletes vault body files
- ❌ Inherits the no-ghostwriting zone (never drafts messages to sensitive recipients)

> ⚠️ **Lesson learned**: don't hand QA for explicitly written rules (frontmatter, status, date, etc.) to an LLM. Overnight LLM QA produces a lot of false positives — replacing it with a deterministic linter (`scripts/vault_lint.py`) is the right call. Use local LLMs only for "preprocessing that can't be done deterministically."

## 📜 Common rules (all agents + Claude Code itself)

Full detail lives under `00_Intranet/AI Operating Rules (Intranet)/`.

1. **🪪 Owner's Identity and philosophy** — always check before acting
2. **No-ghostwriting zone** — the AI never drafts text addressed to sensitive recipients (family, friends, business contacts, etc.) (→ Task Management Rules §3.3)
3. **Money, health, and outbound communication** — human confirmation required. Never proceed on AI judgment alone
4. **Ownership boundaries** — if something is outside your remit, hand off to another agent (don't just handle it in chat — create a task under `04_Tasks/Task Management/Tasks/` and fill in the assignee/comment)
5. **Tasks whose completion criteria can't be written** — turn `ai_judgment_ok` OFF and escalate to a human
6. **Self-QA** — append three lines at the end of your output: fact-check / tone / anti-slop (QA Cycle §10.2)
7. **Dates and titles are mandatory on logs** — when creating a new log, knowledge note, task, etc., always fill in the following frontmatter fields:
   - `date` — the date the content refers to (for transcribed material, the **original date**)
   - `created` — the date the file was actually created (the generation date, if AI-generated)
   - `title` — the same value as the filename is fine, but it must be present and wrapped in `"` (for portability outside Obsidian; checked by vault_lint)
   - If `date` refers to a period rather than a specific day, use the **last day of the period** (for reports, retrospectives, etc. — express the period itself in the filename or a `period:` field)
8. **YAML output rules** — always follow "one independent metadata item per line" and "wrap the entire value in `"` if it contains `:`, `false/true`, or an emoji." Don't cram multiple metadata items into `memo:`. Details → `📋 Common Agent Template.md` §YAML (frontmatter) output rules
9. **Inbox information migration rule** — an inbox file doesn't need to be deleted once `status: done`. However, **the information it holds must be migrated to its proper home (knowledge, log, Project hub, task, etc.) before marking it done**. Details → Task Management Rules §3.8
10. **Continuous updates to intranet files** — if something about the owner's self-referential information comes up naturally in conversation (change of job/role, a new Area, an articulated value, a change to a forbidden zone, a new key person, etc.), propose an update in one line at the end of the conversation (e.g., "Should I update the 〈occupation〉 field in Identity.md?"). **Never rewrite without confirmation.** Targets: `🪪 Identity.md` / `Philosophy & Values.md` / `Design Language.md`, and the hub files under `05_Areas/`.
11. **🛑 Stop rule** — if you hit an auth/permission error, a fatal error, an external connection failure, the same error twice in a row, oversized input, or insufficient information, **stop trying and stop retrying**, and output only 5 items (where you stopped / the verbatim error text / your best guess at the cause / what the human needs to check / a minimal prompt to resume). Never repeat the same operation more than 3 times. Details → `🛑 Stop Rule (Stop Conditions).md`
12. **Pre-creation rule (plan first, reuse existing assets)** — never jump straight into creating something new. First look for existing assets to reuse (templates, past similar deliverables, existing scripts); if the scope is large (roughly: 3+ new files, or introducing a new format), present a plan before starting and get confirmation. Details → `📋 Common Agent Template.md` §Pre-Creation Rule
13. **AI's attitude (don't just go along with it)** — ask when something's ambiguous, and if an instruction/premise seems off or you think there's a better approach, **state your objection or alternative once, before starting**. If told "go ahead anyway," comply. Don't fill the conversation with agreement and praise. Details → §AI's Attitude
14. **Learning from failure** — once a failure/stoppage is resolved, record "what happened + what fixed it + where it applies" as fact (no speculative root-causing) in `📚 Lessons Learned.md`. Propose promoting it to a rule once the same type of issue happens 3 times. Details → 🛑 Stop Rule §S.4
15. **Recording rule (preserve reusable information)** — reusable information that comes up in conversation or work (important decisions and their reasoning, discarded ideas, ideas) should be saved to its proper home as a note, without being asked. If unsure, put it in the inbox. Details → §Recording Rule
16. **✂️ Work discipline (simplicity first, done means verified)** — don't add unrequested content or pad out structure. Don't call something "done" just because it "feels fixed" — verify anything that can be verified mechanically, and **explicitly state verified vs. unverified** in your report. Code is held to an even stricter standard (don't touch anything outside the requested scope, minimal code, reproduce → fix → pass verification, UTF-8 BOM for PS1). Details → `✂️ Work Discipline.md`

## 🧭 Type-driven PARA operations

Express the PARA framework **through the `type` property rather than strict physical folders**. Obsidian's Bases + wikilinks + properties are powerful, so an attribute-driven approach is more flexible than a folder-driven one.

### Mapping between PARA and physical folders

| Physical | Role | type value / identification |
|---|---|---|
| `03_Projects/Projects/` | **P**: a bundle of tasks with a deadline | `type: project` |
| `04_Tasks/Task Management/Tasks/` | one-off actions | (task) |
| `05_Areas/<area>.md` | **A**: area hub + view | (Area hub) |
| `06_Resources/Resources/Knowledge/` | **R**: reusable knowledge | `type: 📕Book/📰Article/📜Principle・Rule/🎮Game/🎵Music etc.` |
| `07_Logs/Logs/` | chronological record | (log) |
| `08_Archive/` | **physical archive reserved for relics only** | (old physical storage) |

### Cross-cutting properties

- `status:` — **standardized to English, hyphen-separated**. Value set differs per DB:
  - Task DB: `todo` / `in-progress` / `done` / `on-hold` / `cancelled`
  - Inbox: `new` / `routing` / `done` / `pending` / `on-hold` / `rejected`
  - Knowledge DB: `inbox` / `in-progress` / `done` / `archived`
  - **`status: archived` is the sacred, immutable value shared by all DBs** — set it and the item is automatically hidden from every base view
- `area:` — plain text using an Area name you've defined yourself (list format if multiple)
- `parent:` — link to a Project with `"[[Project name]]"`
- `date:` / `created:` — the date the content refers to / the file creation date

### Archiving

**Decision rule: do you view this file through a base view (inline database), or by opening a folder directly?**

- **Base-view items (task DB, knowledge DB, log DB, inbox DB, etc. — the DBs under 03/04/06/07)**: leave it in place and set `status: archived`. Don't physically move it. Links stay intact, it stays searchable, and every base view auto-hides it with `status != "archived"`
- **Direct-reference files/folders with no base view (rule collections and guides under `00_Intranet/`, etc.)**: once no longer used, **physically move it to `08_Archive/`** (since no filter hides it, leaving it in place means stale files keep showing up when the folder is opened directly)
- `08_Archive/` holds relic-level physical storage plus the direct-reference archive described above

### Deciding between Log and Resource

When unsure, ask: **"does the date's specificity determine the meaning?"**
- Yes → Log (a snapshot of that day, not reproducible)
- No → Resource (reusable knowledge, where the date is incidental)

### How Projects are handled

Efforts where multiple tasks, logs, and knowledge notes bundle together into something meaningful become a Project at `03_Projects/Projects/<name>.md`. Contents: goal, scope, related links, and a base codeblock (aggregated via `parent.contains("Project name")`). On completion: `status: done` → after some time, `status: archived`. No physical move needed.

## 📂 Working with the task DB

- Each task is a single file at `04_Tasks/Task Management/Tasks/<title>.md`
- "Status, priority, due date, assigned agent, Area" are recorded in frontmatter
- Example extraction logic: Glob `04_Tasks/Task Management/Tasks/*.md` → Grep to extract status/due date/priority → sort by "overdue → due today → due this week → high priority"
- Create new tasks with Write; update existing tasks by editing the relevant line with Edit

## 📂 Working with Areas

Areas are operated as **a single hub `.md` only**. No exceptions.

- One file, `05_Areas/<area>.md`, represents the entire Area (prose + base codeblock)
- **Never create a folder under an Area**. Once a sub-page is needed, it must go into one of the three DBs:
  - **Actions with a completion state** → `04_Tasks/Task Management/Tasks/`
  - **Dated records, events, analysis reports** → `07_Logs/Logs/`
  - **Things learned, books, principles, rule collections** → `06_Resources/Resources/Knowledge/`
- Each entry's `area` property automatically links it into the Area hub's base table
- Resources' `type` list: 📕Book / 📰Article / 🎮Game / 🎵Music / 📺Movie etc. / **📜Principle・Rule** (behavioral guidelines, operating rules) / **👤Person** (person nodes, contact facts)
- Person note naming: `<name>.md`. One file per person. `area:` is the Area name that person is linked to

## 🌐 Using the URL inbox

1. Create a new `01_Inbox/Inbox/<title>.md` and fill in the frontmatter:
   ```yaml
   ---
   title: "<title>"
   type: 🔗URL
   url: https://...
   area: "<Area name>"  # optional (@knowledge will infer it)
   status: new
   date: YYYY-MM-DD
   created: YYYY-MM-DD
   ---
   ```
2. The inbox monitor (scheduled) auto-detects it → hands off to `@orchestrator` → `@knowledge`, which creates a note under `06_Resources/Resources/Knowledge/` and wikilinks it to existing notes

For immediate processing, invoke `@knowledge <URL>` directly.

## 🗣 Conversational curation (refining the vault through conversation)

A mechanism for handling "resolving ambiguity, deeper understanding of a person or relationship, cross-file linking" — things asynchronous one-shot processing can't reach — through **front-channel chat conversation**. Invoked with the `/scan` skill.

- **Targets**: concept nodes / person notes / knowledge notes / logs / Areas / tasks (task status changes and Area policy updates require owner confirmation — confirmed in conversation before being applied)
- **Two phases**: ① Conversation (fill in ambiguity through questions. **Files are not edited**; pending changes accumulate in `01_Inbox/Edit Queue/<topic>-<date>.md`) → ② once the owner says "apply it," `@knowledge`'s reflect mode applies the edit queue in a batch
- **Inherits the no-ghostwriting rule**: never drafts text addressed to sensitive recipients (inherited from §3.3)
- Detailed procedure → `.claude/skills/scan/SKILL.md`; reflect-mode spec → `.claude/agents/knowledge.md`

## 🔗 Wikilink operating policy (two-layer link strategy)

### Layer 1: Structural connections (frontmatter wikilinks)

When creating or editing a new file, the following properties must always be written as `[[]]` wikilinks:

| Property | Role | Example |
|---|---|---|
| `children:` | parent → child (a task's breakdown targets) | `children:\n  - "[[<child task name>]]"` |
| `parent:` | child → parent (a task's consolidation source) | `parent: "[[<project name>]]"` |

**Write the `area` value as plain text, using an Area name you've defined yourself** (no wikilink needed; it should match the filename of a `.md` under `05_Areas/`). If nothing applies, leave `area:` empty (don't use "other" or "general," etc.).

**`area:` / `category:` / `agent:` / `status:` etc. stay plain** (enum-style values, no linking needed).

### Layer 1.5: Concept nodes (concept layer)

Place small notes for recurring themes, principles, and insights under `06_Resources/Resources/Concepts/`. These become the graph's **semantic hubs**.

- Frontmatter: `type: 📜Principle・Rule` / `area:` / `created:`
- Body: a 1–2 line definition + `## Where It Appeared` (3–5 links to logs/tasks) + `## Related Concepts`
- **When to create one**: once the same theme has appeared in 3+ files. The AI may create these without confirmation

### Layer 2: In-body wikilinks (manual, selective)

Only add `[[...]]` in the body **when there's an explicit relationship**. Don't add them mechanically.

> ⛔ **Exception (logs)**: never create wikilinks in the body of agent execution logs or work reports (use plain text in logs under `99_System/agent-runs/` and in report bodies — `[[]]` in logs pollutes the graph). Structural frontmatter properties may still be wikilinks as usual.

### Layer 3: MOC (Map of Content)

Theme-based curation goes in `00_Intranet/MOC/<theme>.md`. The AI never creates MOCs on its own (this is a manually curated zone). A MOC that grows large can be promoted to a Project under `03_Projects/`.

## 🛠 Operating principles as Claude Code

- If a request from the user (the owner) matches a **specific agent's role**, invoke it with `@<agent>`
- Requests like "organize this note," "turn this into a task," "route this" go to **`@orchestrator`**
- Even when executing directly, respect each agent's definition (`.claude/agents/`) and the constitution (`00_Intranet/`)

## ⚙️ Scheduled triggers

Run unattended via a scheduler (the `\Claude\` folder in Windows Task Scheduler, or cron on macOS/Linux). **On Windows, run the bundled `scripts/register-scheduled-tasks.ps1` once with administrator privileges to register everything below in one shot** (nothing runs automatically until you do). Setup steps → `docs/en/AUTOMATION.md`. Recommended set below:

| Task name (example) | Schedule | Prompt / process |
|---|---|---|
| `Claude-NewsDigest` | Every morning at 7:20 | `python scripts/news_fetch.py`: Claude picks what matters from the new items in your feeds (`99_System/news/feeds.json`) and shows it on the dashboard's `/news` |
| `Claude-InboxSweep` | Every 3 hours | `@orchestrator Route unprocessed files in 01_Inbox/ and fill in properties` (**routine, so use `--model haiku` to cut cost**) |
| `Claude-TaskDispatch` | Daily at 12:30 | `task_dispatch.ps1`: **task dispatch run**. An internal delivery that has the responsible agent (knowledge/researcher/specialized) execute tasks marked `ai_judgment_ok: true` and todo/in-progress (max 3 per run; orchestrator §🚚 is authoritative) |
| `Claude-VaultLint` | Daily at 00:05 | `scripts/vault_lint.py` (Python, no LLM, designed for 0% false positives): deterministically checks frontmatter/area/status/date/dead links, and outputs a daily report to `99_System/qa/` |
| `Claude-NightQA` | **Twice a week (Wed/Sun) at 2:00** | `@infrastructure Check the agent run logs and update the summary` (Sunday only also runs the weekly operational improvement scan). Reduced from daily to twice weekly so the monitoring itself doesn't balloon |
| `Claude-WeeklyReview` | Every Sunday at 18:00 | Prepares weekly data (the review body is written interactively via the `/weekly-review` skill) |
| `Claude-KnowledgeEnrich` | Every Sunday at 20:00 | `@knowledge Run in maintenance mode` (knowledge wikilink upkeep, stale-content detection) |

> **Example schedule if you add a specialized agent**: a finance agent → daily at 8:30 (script-side logic ensures it only runs once a day) generating a monthly report, etc.

**Session-limit retry**: for every task, configure "retry after 30 minutes, up to 3 times on failure" using the scheduler's native feature (→ `docs/en/AUTOMATION.md`).

The PS1/Python files invoked by the scheduler are managed outside the vault:
- For Claude Code: `<WORKSPACE>\vault-scripts\` (copy the bundled `scripts/vault_lint.py` here to use it)
- For Local AI (optional): `<LOCAL_AI_DIR>\`

## 💬 Communication history management policy (optional)

If you bring exported data from an external service (messaging app, etc.) into the vault:

- **Never put raw data in the vault**. Store it in a directory outside the vault; only analysis/retrospective logs go in the vault
- Avoid automated processing of sensitive conversations. Manual triggering should be the default
- The owner must always review the output (to prevent AI misreading or fabrication)

### Person notes (👤Person)

Placed under `06_Resources/Resources/Knowledge/` with `type: 👤Person`. Linked as a wikilink via `person: "[[Name]]"` in a log's frontmatter. Auto-aggregated in Obsidian's backlinks panel. If a log's frontmatter `date` covers a period, use the **last day**.

## 📅 Operating phases (record your own change history)

> ⚠️ **This section is a template.** Record changes to your own vault as Phases (a culture of preserving decision-making history).

**Phase 1 (initial setup)** — started YYYY-MM-DD

- Started with the 4 core agents (orchestrator / researcher / knowledge / infrastructure)
- Defined the PARA structure, task DB, inbox, and log DB

**Phase 2 (expansion)** — started YYYY-MM-DD (optional)

- Record here if you add specialized agents
- Also record here if you add/retire Areas or add scheduled triggers
</content>
