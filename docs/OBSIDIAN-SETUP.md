# Obsidian Setup / Obsidian 設定ガイド

> **TL;DR (EN)** — Plugins and core settings that make this vault work: **Templater** (auto-inserts `created`/`date` and applies folder templates), **Obsidian Linter** (auto-updates `updated` on save), relative-path links, and an inbox-by-default new-note location. Set these once per device (`.obsidian/` is gitignored, so each device configures its own).

このVaultを快適に回すための Obsidian 設定。一度設定すれば恒久的に効く。優先度順。
`.obsidian/community-plugins.json` はリポに含めています。このフォルダを Obsidian で vault として開くと「**これらのプラグインを有効化しますか？**」と自動で聞いてくれます。それ以外の設定（テーマ・UIパネル位置等）は `.gitignore` 対象のため**各端末で個別に設定**してください。

---

## 🔴 最優先（自動日付に必須）

### 1. Templater（コミュニティプラグイン）

**何ができるか**: ノート作成時に `created` / `date` / `updated` を自動挿入。フォルダごとにテンプレートを自動適用。

**インストール**: 設定 → Community plugins → Browse → "Templater" → Install → Enable

**設定**:
1. 設定 → Templater
2. **Template folder location**: `_Templates`
3. **Trigger Templater on new file creation**: ON
4. **Folder templates** に追加：

| Folder | Template |
|---|---|
| `02_Tasks/タスク管理/タスク` | `_Templates/タスク.md` |
| `09_Logs/ログ` | `_Templates/ログ.md` |
| `05_Resources/Resources/ナレッジ` | `_Templates/ナレッジ.md` |
| `07_Inbox/インボックス` | `_Templates/インボックス.md` |

設定後、上記フォルダで新規ノートを作ると `created` / `date` が自動で入る。

### 2. Obsidian Linter（コミュニティ）

**何ができるか**: 保存のたびに `updated` を今日の日付へ自動更新。

**設定**: 設定 → Linter → YAML → **YAML Timestamp** を ON

| 設定項目 | 値 |
|---|---|
| Date Created Key | `created` |
| Date Modified Key | `updated` |
| Date Format | `YYYY-MM-DD` |
| Insert on file creation | ON |
| Update on file modification | ON |

---

## 🟠 強く推奨

### 3. Files & Links（コア）

| 設定項目 | 推奨値 | 理由 |
|---|---|---|
| Default location for new notes | `07_Inbox/インボックス` | 行き先不明のノートをインボックスへ |
| New link format | **Relative path to file** | Vault を移動・同期しても壊れない |
| Automatically update internal links | ON | リネーム時にリンク自動更新 |
| Default location for attachments | subfolder `assets` | 画像が散らからない |

### 4. Editor（コア）

| 設定項目 | 推奨値 |
|---|---|
| Default editing mode | Live Preview |
| Readable line length | ON |
| Show frontmatter | OFF（プロパティUIで管理） |
| Fold heading / Fold indent | ON |

### 5. Core plugins（有効化）

Backlinks / Outgoing links / **File recovery（必ずON）** / Bookmarks / Tag pane。

### 6. Bases（コア・新しめのObsidian）

`area` / `parent` / `status` などのプロパティで動的な表を作るのに使う。各 Area ハブ・Project ハブの集約ビューは Bases コードブロックで書く（このリポの `_example-*.md` 参照）。

---

## 🟡 あると便利

- **QuickAdd** — ホットキー一発で「タスク追加」「ログ追加」。Template path＋保存先＋ファイル名フォーマットを設定すると、作成まで3秒。
- **Recent Files** / **Another Quick Switcher** — ナビ強化。
- **テーマ**: Minimal / Things / AnuPpuccin など好みで。

---

## ⚙️ Vault固有の注意

- `_Templates/` は 設定 → Files & Links → Excluded files に追加するとグラフ・検索から除外できる（任意）。
- Templater 構文（`<% tp.date.now() %>`）は Templater 有効時のみ展開される。`_example-*.md` は静的日付で書いてあるので、そのまま読める。

---

## 📋 チェックリスト

- [ ] Templater：インストール・フォルダテンプレート設定
- [ ] Obsidian Linter：YAML Timestamp 設定
- [ ] Files & Links：new note → インボックス／relative path／auto-update links
- [ ] File recovery → ON
- [ ] （任意）`_Templates` を Excluded files に追加
