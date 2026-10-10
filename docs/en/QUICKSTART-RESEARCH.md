# 🔬 Quickstart for researchers

**Keep up with the literature without losing track of what you're doing** — this page sets up only those two things.

The full SHUKI setup runs unattended jobs on a schedule. **You don't need that.** This page gets you:

- 📋 **A task board** — see what you have to do, as a kanban
- 📰 **A paper feed** — pull the new arXiv papers in your area, whenever you feel like it
- 🔍 **`/research`** — dig into one topic and get a map of the prior work

You will **not** set up any scheduled jobs (Task Scheduler / cron). You run a command when you want something. Your machine doesn't need to stay on.

> For the big picture, see the "🎚 How far you take it" section of the [README](../../README.en.md). This page is the **A → B** route.

---

## 1. Install (~15 min)

| # | Step |
|---|---|
| 1 | Install [Claude Code](https://docs.claude.com/en/docs/claude-code/overview) — **a paid plan is required**. This is the main interface |
| 2 | Install [Obsidian](https://obsidian.md/) — the viewer for reading notes and browsing the graph |
| 3 | Check you have [Python 3](https://www.python.org/downloads/) (`python --version`). Used by the task board and the paper feed. No extra packages needed |
| 4 | Get this repository |

**Getting the repository** — if it's public:

```bash
git clone https://github.com/sflren6741/SHUKI my-vault
```

If you were invited to it while it's still private, the easiest route is **Code → Download ZIP** while logged into GitHub (`git clone` would need authentication set up first). The extracted folder becomes your vault.

**Open it**: in Obsidian, choose "Open folder as vault" and select that folder.

## 2. Make it yours (all in chat)

Start Claude Code from the vault folder and type `/setup`.

```bash
cd my-vault
claude
```

```
/setup
```

It asks for your name, what you care about, and your Areas (the domains you keep coming back to). You never edit a file by hand. **For a researcher, Areas like "Research", "Teaching", "Health", "Life" are a good starting set** — you can add more later.

The bundled `_example-*.md` files exist to show how the properties are used. Delete them once they make sense.

**Swap the four hub notes to English** — these are the notes you actually open in Obsidian (task DB, inbox, areas, resources):

```powershell
Copy-Item docs\en\vault-skeleton\タスク管理.md 04_Tasks\  -Force
Copy-Item docs\en\vault-skeleton\インボックス.md 01_Inbox\ -Force
Copy-Item docs\en\vault-skeleton\Areas.md       05_Areas\ -Force
Copy-Item docs\en\vault-skeleton\Resources.md   06_Resources\ -Force
```

The folder names stay Japanese on purpose — the scripts address them by path, so renaming breaks the dashboard. Details in [vault-skeleton/README.md](vault-skeleton/README.md).

## 3. Bring up the task board

One setting. Copy `scripts/shuki_paths.example.json` to `scripts/shuki_paths.json` and put your own folder in `vault`.

```bash
cd scripts
cp shuki_paths.example.json shuki_paths.json   # copy, on Windows
```

```json
{
  "vault": "C:\\Users\\you\\my-vault",
  "lang": "en"
}
```

`"lang": "en"` renders the dashboard UI in English (omit it and you get the Japanese original). Your own notes stay in whatever language you write them in — only the interface is translated. Translations live in `scripts/i18n/en.json`; a missing entry falls back to the original text rather than breaking the page, so you can add your own as you go.

Start it:

```bash
python scripts/dashboard_server.py
```

Open <http://127.0.0.1:8765/board> for the kanban. **Stop it with Ctrl+C when you're done** — it isn't meant to run permanently, and your data stays in the vault as Markdown either way.

Adding tasks is faster from Claude Code:

```
"Add a task: reply to the reviewer comments by Friday"
```

> ℹ️ `/board` and `/news` are translated, including the filter, sort and grouping controls and the task detail panel. Two things stay Japanese by design: the ten built-in Area names and the priority values `高/中/低` — those are *data*, matched against what your notes contain, so translating them would break the colour coding. Your own Areas and priorities show up exactly as you write them. The dashboard home page (`/`) is still largely Japanese; use `/board` as your entry point.

## 4. Set up your paper feed

Register your topic as an arXiv search.

```bash
python scripts/news_fetch.py --init-feeds research --topic "graph neural network"
```

That writes `99_System/news/feeds.json`. **Registering several topics is the point** — open the file and add to `feeds` (copy the `url` the command generated and change the search terms):

```json
{
 "interests": "New papers close to my own research. I care about methodological novelty, reproducibility, and whether I could adopt it in my own experiments",
 "feeds": [
  {"name": "arXiv: graph neural network", "url": "http://export.arxiv.org/api/query?search_query=all%3A%22graph+neural+network%22&sortBy=submittedDate&sortOrder=descending&max_results=15", "category": "Papers"},
  {"name": "arXiv: cs.LG new", "url": "https://rss.arxiv.org/rss/cs.LG", "category": "Papers"}
 ]
}
```

`interests` is your instruction for **what counts as important**. The more specific it is, the better the selection gets (e.g. "Theoretical work on identification conditions in causal inference. Prefer methods papers over applications").

**Fetch:**

```bash
python scripts/news_fetch.py
```

It collects what's new and has Claude pick out what matters. Results show up at <http://127.0.0.1:8765/news>.

### Why you don't have to run it daily

It remembers which URLs it has already shown you, so **running it after three days gives you all three days of new papers**. Nothing is silently dropped. It's built to be run whenever you feel like it, which is why setting up a scheduled job can wait.

> ⚠️ Subject-wide feeds (`cs.LG` and friends) carry hundreds of entries a day, and only the first 5 get read. That's fine as **ambient awareness of the field**, but if you're tracking something deliberately, add more search queries instead.

## 5. Go deep

Where the feed above keeps you from missing work close to yours, `/research` is for **mapping territory you don't know yet**.

```
/research contrastive learning for graph representation
```

It pulls literature from OpenAlex, arXiv, and web search, then returns a report covering related work, **the gaps nobody has filled**, a taxonomy tree, and a diagram of how the work relates (Mermaid). Useful when you're entering a new topic, or before writing a proposal or an introduction.

---

## Later (skip unless you want it)

| When you want to | Look at |
|---|---|
| Keep structured notes on papers you've read | Tell Claude Code "turn this URL into a knowledge note" |
| Have new papers fetched automatically | [AUTOMATION.md](AUTOMATION.md) (Tier C — including a "catch up when I open my laptop" setup) |
| Read the vault on your phone | [MOBILE-SYNC.md](MOBILE-SYNC.md) |
| Tune how Obsidian displays things | [OBSIDIAN-SETUP.md](OBSIDIAN-SETUP.md) |
| See what commands exist | Each folder name under `.claude/skills/` is a `/` command. When unsure, just ask in plain words |

## If something goes wrong

| Symptom | What to do |
|---|---|
| `python` not found | On Windows try `py`. Otherwise reinstall Python and tick "Add to PATH" during setup |
| Dashboard is empty | You just don't have tasks yet. Ask Claude Code to "add a task: …" and reload |
| `/news` is empty | Either you haven't run `python scripts/news_fetch.py` yet, or nothing was new. The reason is logged in `99_System/agent-runs/news_fetch_<date>.log` |
| A feed returns nothing | Open the `url` from `feeds.json` in a browser and check it responds. arXiv searches can break if the query contains punctuation |
