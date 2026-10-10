# 04_Tasks — タスクDB

1ファイル1タスク（`タスク管理/タスク/` 配下）。frontmatter が状態を持つ：`status`（todo / in-progress / done / on-hold / cancelled）/ `priority` / `due` / `area` / `agent`（担当エージェント）/ `ai_judgment_ok`（AI自律実行の可否）/ `completion_criteria`（完了条件）。各エージェントは自分宛タスクを拾って状態を更新する。`タスク管理.md` がインライン Bases ビュー付きのハブ。

> テンプレート：`_Templates/タスク.md`。骨組み例：`タスク管理/タスク/_example-task.md`。
