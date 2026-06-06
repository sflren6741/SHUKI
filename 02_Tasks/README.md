# 02_Tasks — Task DB / タスクDB

**EN** — One Markdown file per task under `タスク管理/タスク/`. Frontmatter carries the state: `status` (todo / in-progress / done / on-hold / cancelled), `priority`, `due`, `area`, `agent` (which agent owns it), `ai_judgment_ok` (may an agent act autonomously?), and `completion_criteria`. Agents pick up tasks assigned to them and update status here. `タスク管理.md` is the hub with an inline Bases view.

**JP** — 1ファイル1タスク（`タスク管理/タスク/` 配下）。frontmatter が状態を持つ：`status` / `priority` / `due` / `area` / `agent`（担当）/ `ai_judgment_ok`（AI自律実行の可否）/ `completion_criteria`（完了条件）。各エージェントは自分宛タスクを拾って状態を更新する。

> Template: `_Templates/タスク.md`. Skeleton example: `タスク管理/タスク/_example-task.md`.
