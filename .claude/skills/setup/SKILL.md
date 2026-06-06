---
name: setup
description: 初回セットアップ。Identity・価値観・Areas・CLAUDE.mdのパス設定・Obsidianプラグイン案内・自動化スクリプト生成をヒアリングで完結させる。「セットアップ」「初期設定」「/setup」で起動。ファイルを直接編集しなくても設定が完了する。
---

# 🚀 初回セットアップ（対話型）

このスキルは**ファイルを直接編集しなくてもvaultの初期設定を完了**させる。質問に答えるだけで全設定が整う。

---

## 🧭 フロー概要

```
Phase 1: 現状確認（未設定箇所を検出）
Phase 2: 基本プロフィール（Identity.md）
Phase 3: 価値観・原則（哲学・価値観.md）
Phase 4: 生活領域（05_Areas/ にハブファイルを作成）
Phase 5: パス設定（CLAUDE.md の <WORKSPACE> 等を置換）
Phase 6: Obsidian プラグイン設定（インタラクティブ案内）
Phase 7: 自動化スクリプト（任意・.ps1 生成）
Phase 8: 専門エージェント（任意）
Phase 9: 完了サマリー
```

各フェーズは**1〜2問ずつ**。一気に全項目を聞かない。
確認なくファイルを書き換えない（必ず完成形を見せてから書き込む）。

---

## Phase 1: 現状確認

以下を読んで未設定箇所を洗い出す：

| ファイル | チェック内容 |
|---|---|
| `00_Intranet/AI運用ルール集（イントラ）/🪪 Identity.md` | `<...>` が残っているか |
| `00_Intranet/AI運用ルール集（イントラ）/哲学・価値観.md` | `<...>` が残っているか |
| `00_Intranet/AI運用ルール集（イントラ）/デザイン言語.md` | `<...>` が残っているか |
| `CLAUDE.md` | `<WORKSPACE>` / `<LOCAL_AI_DIR>` / `<HOME>` が残っているか |
| `05_Areas/` 配下 | `_example-area.md` しかなければ Areas 未作成 |

検出結果を1行で報告してから Phase 2 に進む：
```
✅ 検出完了：Identity に 7箇所、価値観に 10箇所、CLAUDE.md に 3箇所のプレースホルダーが残っています。
順番に設定しましょう。約10〜15分で完了します。
```

すでに設定済みの項目はスキップして未設定分だけ聞く。

---

## Phase 2: 基本プロフィール（Identity.md）

**2問ずつ**聞く。全部答えてもらったら Identity.md の完成形を見せて確認を取ってから書き込む。

| # | 質問 |
|---|---|
| 1 | 「名前（または呼び名）を教えてください。AIにどう呼んでほしいですか？」 |
| 2 | 「主に使う言語とタイムゾーンは？（例: 日本語、Asia/Tokyo）」 |
| 3 | 「職業や役割を簡単に教えてください。細かくなくていいです。」 |
| 4 | 「AIに前提として知っておいてほしいスキルやツールはありますか？」 |
| 5 | 「今の人生フェーズや、特に打ち込んでいることを教えてください。」 |
| 6 | 「行動の軸になっている価値観を2〜3語で教えてください。（例: 誠実さ・成長・自律）」 |
| 7 | 「AIに書かせたくない・判断させたくない領域はありますか？（例: 特定の相手へのメッセージの代筆、金融取引の実行）」 |

全項目揃ったら完成形を表示 → 「これで保存しますか？」→ OK なら Edit で書き込む。

---

## Phase 3: 価値観・原則（哲学・価値観.md）

Identity の「価値観のキーワード」をベースに深掘りする。

| # | 質問 |
|---|---|
| 1 | 「先ほどの価値観キーワード（例: 誠実さ）それぞれについて、AIが判断に使えるよう1〜2文で定義してもらえますか？」 |
| 2 | 「人間関係・仕事・趣味など、大切にしている領域での行動原則があれば教えてください。（例: 人間関係：約束は小さくても守る）」 |
| 3 | 「AI（自分）が絶対にやらないこと・嫌いなことはありますか？（例: 曖昧なまま進める、過剰な礼儀）」 |

全項目揃ったら完成形を表示 → 確認 → Edit で書き込む。

> 「あとで考えたい」「今は省略」も可。その場合は `<後で追記>` と仮置きして先に進む。

---

## Phase 4: 生活領域（Areas）

> 「管理したい生活領域を教えてください。（例: 仕事・健康・英語学習・趣味・人間関係・家計）」

回答をもとに `05_Areas/<area名>.md` を以下のテンプレートで作成：

```markdown
# <Area名>

## 概要

<Area の目的・スコープを1〜2行>

## フォーカス

- （現在の課題・目標を追記していく）

## ビュー

\`\`\`base
filters:
  area:
    contains: "<Area名>"
\`\`\`
```

作成後、`デザイン言語.md` の Area 一覧もあわせて更新（Area 名と文体メモを記入）。
既存の `_example-area.md` は残す（削除はオーナー判断）。

---

## Phase 5: パス設定（CLAUDE.md）

自動化を使う予定があるか確認：

> 「朝のスタンドアップや夜間QAを自動実行する予定はありますか？（任意・あとでも設定できます）」

**使う予定あり** → 以下のパスを聞いて CLAUDE.md を Edit で置換：
- `<WORKSPACE>` — 作業用フォルダのパス（例: `C:\Users\username\workspace\VSCode`）
- `<LOCAL_AI_DIR>` — Ollama スクリプトのフォルダ（使わない場合は该当行ごと削除を提案）
- `<HOME>` — ホームディレクトリ（例: `C:\Users\username`）

**使う予定なし** → プレースホルダーをそのまま残す（後の Phase 7 でスクリプト生成時に設定可）。

---

## Phase 6: Obsidian プラグイン設定（インタラクティブ案内）

Obsidian の設定は GUI 操作が必要なため、Claude Code が代わりに行うことはできない。
ただし**手順を1ステップずつ案内**し、完了したら次へ進む形で完結させる。

> 「Obsidian を開いてください。プラグイン設定を一緒に進めます。」

### ステップ 1: プラグイン有効化の確認
Obsidian でこの vault を開くと、リポに含まれる `.obsidian/community-plugins.json` から「Templater / Obsidian Linter を有効化しますか？」と自動で聞いてくれる。
→ 「有効化しました」と言ってもらったら次へ。

### ステップ 2: Templater 設定（自動日付挿入に必須）
```
設定 → Templater
  ・Template folder location: _Templates
  ・Trigger Templater on new file creation: ON
  ・Folder templates:
    04_Tasks/タスク管理/タスク  → _Templates/タスク.md
    07_Logs/ログ              → _Templates/ログ.md
    06_Resources/Resources/ナレッジ → _Templates/ナレッジ.md
    01_Inbox/インボックス      → _Templates/インボックス.md
```
→ 「設定しました」と言ってもらったら次へ。

### ステップ 3: Obsidian Linter 設定（`updated` 自動更新）
```
設定 → Linter → YAML → YAML Timestamp を ON
  ・Date Created Key: created
  ・Date Modified Key: updated
  ・Date Format: YYYY-MM-DD
  ・Insert on file creation: ON
  ・Update on file modification: ON
```
→ 「設定しました」と言ってもらったら次へ。

### ステップ 4: Files & Links 設定
```
設定 → Files & Links
  ・Default location for new notes: 01_Inbox/インボックス
  ・New link format: Relative path to file
  ・Automatically update internal links: ON
```

設定完了したら Phase 7 へ。
スキップしたい場合は「後で」と言えば省略可（詳細は `docs/OBSIDIAN-SETUP.md`）。

---

## Phase 7: 自動化スクリプト（任意）

> 「朝のスタンドアップ・夜間QAをスケジュール自動化しますか？スクリプトを生成します。（任意）」

**する場合**：以下のスクリプトを **vault の外のフォルダ**（例: `<WORKSPACE>\vault-scripts\`）に生成する：

```powershell
# run-standup.ps1
Set-Location "<VAULT_PATH>"
claude -p "@orchestrator 朝のスタンドアップを生成" *>> "<HOME>\claude-logs\standup.log"
```

```powershell
# run-night-qa.ps1
Set-Location "<VAULT_PATH>"
claude -p "@infrastructure 稼働ログを確認してサマリーを更新" *>> "<HOME>\claude-logs\night-qa.log"
```

```powershell
# run-inbox-sweep.ps1
Set-Location "<VAULT_PATH>"
claude -p "@orchestrator 01_Inbox/ の未処理ファイルを振り分け・プロパティ補完" *>> "<HOME>\claude-logs\inbox.log"
```

スクリプト生成後、Task Scheduler への登録手順を案内する（登録自体は管理者権限が必要なため手動）：
```
タスクスケジューラ → タスクの作成
  ・朝スタンドアップ: 毎日 7:00 → run-standup.ps1
  ・夜間QA: 毎日 2:00 → run-night-qa.ps1
  ・インボックス巡回: 数時間おき（9:00起点） → run-inbox-sweep.ps1
  ・失敗時リトライ: 30分後・最大3回（設定 → 条件）
```

---

## Phase 8: 専門エージェント（任意）

> 「コア4体に加えて専門エージェントを追加しますか？例：家計管理・語学学習・計画・内省など。（スキップ可）」

追加する場合は役割を聞いて `.claude/agents/<name>.md` を `📋 エージェント共通テンプレート.md` に沿って作成。

---

## Phase 9: 完了サマリー

設定した内容を箇条書きで報告：

```
✅ セットアップ完了！

設定したもの：
- Identity.md（プロフィール・価値観・境界線）
- 哲学・価値観.md（価値観定義・行動原則）
- Areas: 仕事 / 健康 / 英語学習（ハブファイル作成済み）
- CLAUDE.md パス設定（<WORKSPACE> 置換済み）
- Obsidian プラグイン：Templater / Linter / Files & Links 設定済み
- 自動化スクリプト：vault-scripts/ に生成済み（Task Scheduler 登録は手動）
- 専門エージェント：household（家計管理）

次にできること：
- 日常利用を始める → README の「日常の使い方」
- タスクを追加する → 「タスクを作って：<内容>」
- URLをナレッジ化する → 「このURLをナレッジ化して: https://...」
- 朝スタンドアップを確認する → 「@orchestrator 今日のフォーカスは？」
```

---

## 🚫 やってはいけないこと

- ❌ 確認なくファイルを書き換える（必ず完成形を見せてから書き込む）
- ❌ 一度に全項目を聞く（2問ずつ・圧倒させない）
- ❌ Identity.md にパスワード・連絡先等を記入させる
- ❌ 代筆禁止ゾーンに関わる内容を自動で記入する
- ❌ vault 外のパスを vault 内ファイルにハードコードする（スクリプトは vault 外に生成）

## 🔄 セルフQAの3行

```
- 事実チェック: <プレースホルダーが全て置換されたか。書き込み前に確認を取ったか>
- トーン: <親しみやすく、圧倒させていないか>
- アンチスロップ: <聞いていない情報を勝手に補完していないか>
```
