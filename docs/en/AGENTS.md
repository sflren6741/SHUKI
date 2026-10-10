# Agents — how they work & how to make one / How Agents Work and How to Build One

> **TL;DR (EN)** — Each agent is a single Markdown file in `.claude/agents/<name>.md` with YAML frontmatter (`name`, `description`, `tools`) and a body that defines its role, triggers, constraints, and escalation rules. **The file is the source of truth** — editing it changes behavior; editing the README does not. Tool permissions are the real guardrail: a read-only agent literally cannot write. Agents = unattended & routine; **Skills** = interactive & confirmation-required.

---

## 1. Anatomy of an agent

`.claude/agents/<name>.md`:

```markdown
---
name: relationship
description: When to trigger, what it does, and what it doesn't do, in 1–2 sentences. Claude reads this description to decide "should this task be routed to this agent."
tools: Read, Glob, Grep        # The tools granted. Omit Write/Edit to prevent writing
---

# Role (one sentence describing this agent)

## 🧭 Required reading   ← rule files to read before acting (Identity / philosophy, etc.)
## 📖 Role              ← what it does / doesn't do
## ⏰ Trigger timing     ← trigger table
## 🚫 Things it must never do ← prohibitions (boundaries spelled out explicitly)
## 🛑 Escalation         ← the "correct way to stop" when completion criteria can't be met
## 🔄 3-line self-QA     ← self-check appended to the end of output (fact / tone / anti-slop)
```

Key points:
- **`description` is the crux of routing**. The more specifically it states "trigger on X" / "never do Y," the fewer misrouted invocations you'll get.
- **`tools` is the technical boundary**. "Don't let it ghostwrite," "don't let it delete" is guaranteed not by asking nicely in prose but by **not granting the tool** (e.g. `relationship` only has `Read, Glob, Grep` — it's physically unable to write).
- Point the body at "read the constitution (`00_Intranet/`)" so common rules stay centralized in one place.

---

> **The 4 core agents**: `orchestrator` (triage, weekly review, dispatch) / `researcher` (research, comparisons) / `knowledge` (turning content into knowledge, wikilinks) / `infrastructure` (audits, monitoring, read-only). Add specialized agents on top of these to fit your own life.
>
> **There's no dedicated reviewer for QA.** Quality assurance is distributed across "each agent's self-QA (3 lines at the end of output) + owner confirmation in 🔴 zones + deterministic linting (`scripts/vault_lint.py`)." A dedicated reviewer proved heavy relative to how much it was actually used, so we've settled on this distributed model instead.

---

## 2. Source of truth

**Only `.claude/agents/<name>.md` determines behavior.**
The agent lists in `CLAUDE.md` or the README are **summaries (for navigation)** — if they ever disagree, trust `.claude/agents/`. Editing this list doesn't change an agent's behavior unless you also fix the agent list — conversely, **if you want to change behavior, edit `.claude/agents/`**.

---

## 3. Agents vs. Skills

| | Agent | Skill (`.claude/skills/`) |
|---|---|---|
| Nature | Unattended, routine | Interactive, confirmation-required |
| Invocation | `@name` / schedule | `/skill-name` |
| Good for | Triage, QA, routine reports | Weekly review, task audits, sensitive retrospectives |
| Human involvement | Follow-up confirmation | Involved throughout execution |

Sensitive work (relationships, health, money) should be brought **front and center as a skill**, so a human is always in the loop. This is at the core of the design philosophy (the "Boundaries" section in [TIPS.md](TIPS.md)).

---

## 4. Adding a new agent

1. Create a new `.claude/agents/<name>.md`. Fastest to copy an existing core agent (e.g. `knowledge.md`) as a template.
2. Write the frontmatter:
   - `name`: must match the filename
   - `description`: trigger conditions and prohibitions (**the most important part**)
   - `tools`: keep to the bare minimum. `Read, Glob, Grep` for read-only agents
3. Write the body: "required reading / role / triggers / prohibitions / escalation / self-QA."
4. (Optional) Add a one-line entry to the agent list in `CLAUDE.md` and the README (for navigation).
5. Add a one-line note to `orchestrator` saying "route requests of this kind to the new agent," so routing works end to end.

> If you want to use different models for different agents, design it around the role — lightweight model for light routine work, top-tier model for strategic judgment (see this repo's `💰 Model Strategy`). Claude Code lets you specify a model per agent (the mechanism varies by version, so check the official docs).

---

## 5. Handoffs

When an agent's work goes beyond its own remit, it should **not hoard it in chat** — it creates a task and hands it to another agent (creates a task under `04_Tasks/`, filling in the assignee and comment). This keeps work from getting buried in chat and makes it trackable. `orchestrator` directs this traffic.

**Task dispatch run (§🚚)**: scheduling `orchestrator` to run once at midday has it automatically execute any todo/in-progress task with `agent:` set and `ai_judgment_ok: true` via the assigned agent (max 3 per run). This lets qualifying tasks get done by AI hands without the human needing to give the instruction every time. 🔴 zones (money, health, outbound communication, ghostwriting) are excluded.

---

## 6. The "correct way to stop" / Escalation

When completion criteria can't be written, or a request crosses a boundary, **stopping is the correct behavior**. Turn `ai_judgment_ok` OFF and escalate to a human. This is central to keeping agents from running out of control.
</content>
