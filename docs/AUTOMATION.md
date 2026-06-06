# Automation — scheduled routines / 定期実行

> **TL;DR (EN)** — Run Claude Code headlessly on a schedule (Windows Task Scheduler / cron) to generate a morning standup, a weekly review, nightly QA, and inbox routing. A small wrapper script invokes `claude -p "<prompt>"` from the vault folder. Optionally, a separate local LLM (Ollama) sweeps the vault at night for typos and broken frontmatter. None of this is required to use the system by hand.

エージェントは手動（`@name`）でも使えるが、**スケジュール起動**で「朝・夜に勝手に回る」状態にすると一気に楽になる。

---

## 1. 仕組み / How it works

Claude Code は**ヘッドレス（非対話）実行**できる。vault フォルダで：

```bash
claude -p "@orchestrator 朝のスタンドアップを生成"
```

これをOSのスケジューラ（Windows: Task Scheduler、mac/Linux: cron / launchd）から叩く。
無人実行ではツール許可のプロンプトが出ないよう、`.claude/settings.json` で使うツールを事前許可しておく（許可の付け方は Claude Code 公式ドキュメント参照。バージョンで方法が変わるため、ここでは固定の引数を断定しない）。

---

## 2. 推奨ルーティン / The routines

| ルーティン | 頻度 | プロンプト（例） |
|---|---|---|
| Morning standup | 毎朝 7:00 | `@orchestrator 朝のスタンドアップを生成` |
| Planner reminder | 毎朝 6:30 | `@planner 期限7日前・3日前・当日のタスクをリマインド` |
| Inbox sweep | 数時間おき | `@orchestrator 07_Inbox/ の未処理ファイルを振り分け・プロパティ補完` |
| Night QA | 毎日 2:00 | `@infrastructure 稼働ログを確認してサマリーを更新` |
| Weekly review | 週次 | （対話スキル `/weekly-review` を人間が起動。無人生成しない） |

> センシティブ・要確認のもの（週次レビュー等）は**無人にしない**。スキルとして人間が起動する（[AGENTS.md](AGENTS.md) のエージェント/スキルの棲み分け）。

---

## 3. Windows Task Scheduler の組み方 / Wiring it on Windows

1. ラッパー `.ps1` を vault の**外**に置く（パスや鍵を含めうるので公開リポに入れない）。例：

   ```powershell
   # run-standup.ps1  ※あなたの環境に合わせてパスを変える
   Set-Location "<PATH-TO-YOUR-VAULT>"
   claude -p "@orchestrator 朝のスタンドアップを生成" *> "<PATH-TO-LOGS>\standup.log"
   ```

2. Task Scheduler → タスクの作成：
   - **トリガー**: 毎日 7:00
   - **操作**: `powershell.exe -ExecutionPolicy Bypass -File "<PATH>\run-standup.ps1"`
   - **条件/設定**: 「失敗時に再起動（例: 30分後・最大3回）」を入れておくと、セッション制限・一時失敗に強い。

3. 日本語を含む `.ps1` は **UTF-8 BOM付き**で保存する（Windows PowerShell 5.1 が文字化けで構文エラーになるのを防ぐ）。

> スケジューラが叩く `.ps1` / Python は **vault の外**で管理する（このリポにはエージェント定義とルールだけを置く）。生成された実行ログ（`00_Intranet/agent-runs/` 等）は `.gitignore` 済みでコミットされない。

---

## 4. （任意）ローカル夜間QA — Ollama / Optional local QA layer

vault本体とは別レイヤーとして、ローカルLLM（[Ollama](https://ollama.com/)）に**夜間の誤字・frontmatter チェック**を任せられる。

- 役割: vault を巡回し、誤字脱字・YAML不整合を検出して**レポートを書くだけ**（本文は編集しない）。
- 境界: レポート追記のみ。vault本体の編集・削除・外部送信・センシティブ領域には触らせない。
- 翌朝、`orchestrator` がそのレポートを読んで人間に提示する。

> モデル選定・スクリプトは環境依存。ローカルで完結するのでプライバシーに優しく、APIコストもかからない。必須ではない（手動運用でも全く問題ない）。

---

## 5. 最小構成で始める / Start minimal

全部いきなり組まなくていい。**まず Morning standup だけ**スケジュール化して、効果を感じたら週次・QA・モバイルへ広げるのがおすすめ。
