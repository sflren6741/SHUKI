# Tips & mental models

> **TL;DR (EN)** — A few ideas do most of the work: organize by a `type:` property (not rigid folders); link files with wikilinks in two layers (structural in frontmatter, selective in body); promote recurring themes into "concept nodes" that become graph hubs; render dynamic views with Obsidian Bases; and keep hard boundaries (money/health/relationship messages need a human). Master these and the vault compounds in value.

A handful of ideas do most of the work here. In order:

---

## 1. Relate files with wikilinks

Link notes together with `[[filename]]`. Obsidian treats this as a bidirectional link (backlinks), so **writing one side makes it automatically appear on the other**. Information becomes retrievable by "relationship" rather than "folder location."

The trick is running a **two-layer link strategy**:

- **Layer 1: structural links (frontmatter)** — always write things like `parent:` / `children:` as `[[]]`. This mechanically connects structure — a task's parent/child, its link to a Project, etc.
  ```yaml
  parent: "[[International Trip 2026]]"
  ```
- **Layer 2: body links (manual, selective)** — only add `[[...]]` in the body **when there's an explicit relationship**. Don't add them mechanically (over-linking turns the graph into noise).
  ```markdown
  Related log: [[2026-01-15 What Happened That Day]]
  ```
- **Person links** — writing `person: "[[Name]]"` in a log gathers every mention at that person's node (`type: 👤Person`). Your relationships turn into an automatic ledger.

---

## 2. Type-driven PARA

Express PARA (Projects / Areas / Resources / Archive) **through a `type:` property, not rigid folders**.

- Reclassifying something is **a single property change**, not a folder move → instant, and links never break.
- `type:` examples: `project` / `📕Book` / `📰Article` / `📜Principle・Rule` / `👤Person`...
- **Archiving doesn't move anything either**: just set `status: archived`. It stays in its original place and context, remains searchable, and is automatically hidden from every view.

`status` is standardized per DB (English, hyphen-separated): tasks = `todo/in-progress/done/on-hold/cancelled`, inbox = `new/routing/done/...`, knowledge = `inbox/in-progress/done/archived`. `archived` is the "sacred, immutable value" shared by every DB.

---

## 3. Concept nodes — the graph's semantic hubs

Once the same theme has appeared in **3 or more files**, create a small note under `06_Resources/Resources/Concepts/`.

- A 1–2 line definition, plus links to "Where It Appeared," "Actions It Produced," and "Related Concepts."
- This becomes a **semantic hub** cutting across folders, and grows into a center of the graph visualization.
- Adding an `## Insights` section to an important log and linking it to a concept node automatically ties your day-to-day records back to concepts.

→ The more you use this, the more connected the vault becomes, and "what you keep thinking about" becomes visible.

---

## 4. Dynamic views with Obsidian Bases

Build **dynamic tables** driven by properties like `area` / `parent` / `status`. Drop a Bases codeblock into an Area hub or Project hub and matching notes gather automatically (see `_example-area.md`). You can see "every note in this area" without opening a folder.

---

## 5. MOC (Map of Content) / manual curation

Theme-based entry points go **by hand** in `00_Intranet/MOC/<theme>.md` (a zone the AI never auto-generates into). Examples: "Anime Library," "Relationship Map," "Self-Understanding Map." If Bases is "automatic aggregation," MOC is "a map a human curated."

---

## 6. Boundaries are the point

The single most effective thing about this system is deciding what the AI **isn't allowed to do**.

- **No-ghostwriting zone**: never let the AI write messages or letters to someone important (if you build an agent that handles such recipients, restricting `tools:` to just `Read, Glob, Grep` makes it **technically incapable** of writing — the surest guarantee).
- **Human-confirmation-required zone**: money, health, and outbound communication never proceed on AI judgment alone.
- **Tasks whose completion criteria can't be written**: turn `ai_judgment_ok` OFF and escalate to a human.

Constraints are what make it safe to delegate. This is a philosophy, embedded into every agent definition and rule.

---

## 7. Quick decision rules

- **Log or Resource?** → "Does the date's specificity determine the meaning?" Yes = Log, No = Resource.
- **Is it a task?** → "Can I write a completion criterion?" If not, it's worth considering as an Area or Project item.
- **Create a concept node?** → Once the same theme appears in 3+ files.
- **Add a wikilink?** → Structural links in frontmatter, always; body links, only "when there's an explicit relationship."

---

## 8. Extend it

This template ships with **only a generic skeleton**. Anything that depends on personal data or external integrations can be added once your vault has grown into its own. Common directions to extend:

| What you could add | What it involves | Where to start |
|---|---|---|
| 💰 Household finance review | An interactive skill that reviews monthly income/expenses and net worth from CSVs and pay stubs | Use `/plan` or an existing skill as a template, and add a finance agent following `docs/AGENTS.md` |
| 💬 Message retrospectives | A manual skill that fact-checks exported chat logs (for a specific person only) | Sensitive, so **never run unattended** — always have the person confirm the output |
| 📥 Email ingestion | A script + skill that drops new Gmail messages, etc. into the inbox | Keep credentials outside the vault and gitignored; remove the label after ingestion to prevent re-fetching |
| 📊 Activity reports | Analyzes monthly exports (e.g. Google Takeout) to visualize activity | Keep something like `process_takeout.py` outside the vault, and deep-dive with a skill like `/activity-review` |
| 🔧 Technical maintenance | A skill that diagnoses/repairs scheduler, script, and log integrity | For mechanical "is anything broken?" checks. Operational reviews belong in `/ops-review` |
| 🖼 OCR / voice intake | Local-LLM image OCR / voice transcription → inbox submission | Reserve local LLMs for "preprocessing that can't be done deterministically" (see the lesson below) |

**How to build any of these**: agents go in `.claude/agents/<name>.md` (`docs/AGENTS.md`), skills go in `.claude/skills/<name>/SKILL.md`. Always keep personal data paths and credentials **outside the vault**, and keep them out of the public repo via `.gitignore`.

### Operational lessons (from past mistakes)

- **QA for explicitly written rules should be deterministic code, not an LLM.** Handing frontmatter/status/date checks to an overnight LLM QA process leads to it falsely flagging correct data as a "violation" and trying to "fix" it. That's why we lean on `scripts/vault_lint.py` (deterministic). Reserve local LLMs for preprocessing that can't be done deterministically, like OCR or transcription.
- **Monitoring inflates itself if left unchecked.** Running full operating summaries and QA reports every day makes the reports themselves grow too large to read. Throttle the frequency (e.g. run night QA twice a week) and design for "zero items requiring attention" to be the normal state.
- **Watch out for over-importing your own customizations.** When handing your personally-optimized setup to someone else, port only the generic skeleton, and leave personal settings as blank space to fill in (this repo itself was built following that principle).
</content>
