# English vault skeleton

The four notes you actually open in Obsidian, translated into English.

The rest of the vault skeleton (folder names, `_Templates/`, `00_Intranet/`) stays in Japanese — the bundled scripts address those folders by path, so **renaming them breaks the dashboard**. These four are different: they are content, not paths, so they can be swapped freely.

| File | Replaces | What it is |
|---|---|---|
| `タスク管理.md` | `04_Tasks/タスク管理.md` | Task DB hub (active / due this week / by agent / everything) |
| `インボックス.md` | `01_Inbox/インボックス.md` | Inbox hub (unprocessed / on hold / everything) |
| `Areas.md` | `05_Areas/Areas.md` | Area hub |
| `Resources.md` | `06_Resources/Resources.md` | Knowledge & concept-node hub |

## Install

From the vault root, on Windows PowerShell:

```powershell
Copy-Item docs\en\vault-skeleton\タスク管理.md 04_Tasks\  -Force
Copy-Item docs\en\vault-skeleton\インボックス.md 01_Inbox\ -Force
Copy-Item docs\en\vault-skeleton\Areas.md       05_Areas\ -Force
Copy-Item docs\en\vault-skeleton\Resources.md   06_Resources\ -Force
```

macOS / Linux:

```bash
cp docs/en/vault-skeleton/タスク管理.md   04_Tasks/
cp docs/en/vault-skeleton/インボックス.md 01_Inbox/
cp docs/en/vault-skeleton/Areas.md        05_Areas/
cp docs/en/vault-skeleton/Resources.md    06_Resources/
```

The filenames deliberately stay the same, so the `[[タスク管理]]` style wikilinks scattered through the vault keep resolving. Inside the English versions those links are written as `[[タスク管理|Tasks]]` — same target, English label.

## Notes

- `file.inFolder("04_Tasks/タスク管理/タスク")` and friends are **not** translated. Those are paths.
- The People view matches both `type: 👤人物` and `type: 👤Person`, so it works whichever one your notes end up using.
- Ran into an empty table? That usually means the folder has no notes yet, not that the view is broken.
