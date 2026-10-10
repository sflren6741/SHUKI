# Automation — scheduled routines / 定期実行

> **TL;DR (EN)** — Run Claude Code headlessly on a schedule (Windows Task Scheduler / cron) to fetch the day's News, route the inbox, dispatch autonomous tasks, and run a weekly review. A small wrapper script invokes `claude -p "<prompt>"` from the vault folder. A deterministic linter (`scripts/vault_lint.py`, no LLM) does the frontmatter/status/date QA — don't hand rule-based QA to an LLM (it hallucinates violations). None of this is required to use the system by hand.

> **💡 `/setup` を使う場合** — `/setup` スキルが `.ps1` ラッパースクリプトを自動生成します。このファイルは Task Scheduler への登録手順と詳細リファレンスです。

エージェントは手動（`@name`）でも使えるが、**スケジュール起動**で「朝・夜に勝手に回る」状態にすると一気に楽になる。

---

## 1. 仕組み / How it works

Claude Code は**ヘッドレス（非対話）実行**できる。vault フォルダで：

```bash
claude -p "@orchestrator 01_Inbox/ の未処理ファイルを振り分け・プロパティ補完"
```

これをOSのスケジューラ（Windows: Task Scheduler、mac/Linux: cron / launchd）から叩く。
無人実行ではツール許可のプロンプトが出ないよう、`.claude/settings.json` で使うツールを事前許可しておく（許可の付け方は Claude Code 公式ドキュメント参照。バージョンで方法が変わるため、ここでは固定の引数を断定しない）。

---

## 2. 推奨ルーティン / The routines

| ルーティン | 頻度 | プロンプト・処理（例） |
|---|---|---|
| News digest | 毎朝 7:20 | `python scripts/news_fetch.py`（購読フィードの新着から重要なものを Claude が選び、ダッシュボードの `/news` に出す。フィードの作り方は [QUICKSTART-RESEARCH.md](QUICKSTART-RESEARCH.md) §4） |
| Inbox sweep | 数時間おき | `@orchestrator 01_Inbox/ の未処理ファイルを振り分け・プロパティ補完`（**定型なので `--model haiku` でコスト削減**） |
| Task dispatch | 毎日 12:30 | `@orchestrator タスクディスパッチ便を実行（§🚚）`（AI同士でタスクを進める社内便・最大3件/便） |
| Vault lint（決定的QA） | 毎日 0:05 | `python vault_lint.py --vault <VAULT>`（LLM不使用・`99_System/qa/` に出力。§4） |
| Night QA（稼働サマリー） | **週2回（水・日）2:00** | `@infrastructure 稼働ログを確認してサマリーを更新`（日曜のみ運用改善スキャンも） |
| Knowledge enrich | 週次日曜 20:00 | `@knowledge メンテナンスモードで実行`（wikilink整備・陳腐化検出） |
| Weekly review | 週次 | （対話スキル `/weekly-review` を人間が起動。無人生成しない） |
| （任意）専門エージェント定期実行 | 任意 | `@<専門エージェント> <役割に合わせて>` |

> センシティブ・要確認のもの（週次レビュー等）は**無人にしない**。スキルとして人間が起動する（[AGENTS.md](AGENTS.md) のエージェント/スキルの棲み分け）。
>
> Night QA を毎日でなく週2回に絞っているのは、監視レポート自体が肥大して読まれなくなるのを防ぐため（監視の自己肥大対策）。

---

## 3. Windows Task Scheduler の組み方 / Wiring it on Windows

### 3a. ワンコマンド登録（推奨）

同梱の [`scripts/register-scheduled-tasks.ps1`](../scripts/register-scheduled-tasks.ps1) が、上記ルーティンを**失敗時リトライ付きで一括登録**する。**このスクリプトを1回実行するまで、自動実行は一切起きない**（＝手動で `@orchestrator ...` を呼ぶ必要がある）ので、自動化したいなら最初にこれを走らせる。

1. 決定的QAスクリプトを vault 外へ置く：`scripts/vault_lint.py` を `<WORKSPACE>\vault-scripts\` にコピー。
2. **管理者権限の PowerShell** で実行：
   ```powershell
   & "<リポ>\scripts\register-scheduled-tasks.ps1" -Vault "C:\path\to\your-vault"
   ```
3. 確認とテスト発火（いきなり全任せにしない）：
   ```powershell
   Get-ScheduledTask -TaskPath '\Claude\'
   Start-ScheduledTask -TaskName 'Claude-InboxSweep' -TaskPath '\Claude\'
   ```
   `01_Inbox/` の未処理が振り分けられ、`99_System/agent-runs/inbox_<日付>.log` にログが残ればOK。解除は `Get-ScheduledTask -TaskPath '\Claude\' | Unregister-ScheduledTask`。

パラメタ・登録タスク一覧は [`scripts/README.md`](../scripts/README.md)。日本語入り PS1 は **UTF-8 BOM付き**で保存する（PowerShell 5.1 の文字化け対策・同梱スクリプトは対応済み）。

### 3b. 手動 GUI で登録（スクリプトを使わない場合）

1. ラッパー `.ps1` を vault の**外**に置く。例：
   ```powershell
   # run-inbox.ps1  ※あなたの環境に合わせてパスを変える
   Set-Location "<PATH-TO-YOUR-VAULT>"
   claude -p "@orchestrator 01_Inbox/ の未処理ファイルを振り分け・プロパティ補完" *> "<PATH-TO-LOGS>\inbox.log"
   ```
2. Task Scheduler → タスクの作成：
   - **トリガー**: 毎日 9:00（数時間おきでもよい）
   - **操作**: `powershell.exe -ExecutionPolicy Bypass -File "<PATH>\run-inbox.ps1"`
   - **条件/設定**: 「失敗時に再起動（例: 30分後・最大3回）」を入れると、セッション制限・一時失敗に強い。

> スケジューラが叩く `.ps1` は **vault の外**で管理する（このリポにはエージェント定義・ルール・配布用スクリプトだけを置く）。生成された実行ログ・QAレポート（`99_System/` 配下）は `.gitignore` 済みでコミットされない。同梱の `scripts/vault_lint.py` は vault 外へコピーして使う。

---

## 4. 決定的QA — vault_lint.py（推奨）と任意のローカルLLM

**明文化されたルールのQA（frontmatter 構造・`status`・`date`・デッドリンク等）は、LLM ではなく決定的コードで行う。** 同梱の `scripts/vault_lint.py`（Python・PyYAML のみ・誤検出0%設計）を毎日回し、`99_System/qa/YYYY-MM-DD.md` にレポートを出す。翌朝 `orchestrator` がそれを読んで要対応をトリアージする。

```bash
python scripts/vault_lint.py --vault /path/to/your-vault
```

導入・スケジュール登録は [`scripts/README.md`](../scripts/README.md) を参照。

> ⚠️ **教訓**: 以前は夜間にローカルLLM（Ollama 等）で vault のQAを回す設計も試せるが、**明文ルールのチェックを LLM に任せると誤検出が多く**、正しいデータを「違反」と誤って直そうとする事故が起きやすい。だから明文ルールは `vault_lint.py`（決定的）に寄せている。ローカルLLMは「決定的にできない前処理」（OCR下書き・音声文字起こし等）にだけ使うのが吉。

---

## 5. 最小構成で始める / Start minimal

全部いきなり組まなくていい。**まず Inbox sweep だけ**スケジュール化して、効果を感じたら週次・QA・モバイルへ広げるのがおすすめ。
