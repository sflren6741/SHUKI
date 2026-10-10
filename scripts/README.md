# scripts/

## Public core

The public core provides AI chat, tasks, calendar, News and decision cards. Decision cards are always available for human approvals and information requests; plugin settings cannot disable them. Encyclopedia, visualization, games, finance and other specialized features are optional and omitted from this package. Shared file access, settings and privacy checks support these workflows. The core Home page opens the task board with the shared chat panel. Decision records and response history stay in the private vault's `99_System/decisions/`; the public package includes only their code.

Run `dashboard_server.py` with Python 3.11 or later. Set `SHUKI_VAULT` to an absolute vault path and optionally `SHUKI_DATA_DIR` to an absolute directory outside the code tree. Fresh runtime stores are created there; populated legacy stores remain authoritative until an explicit verified migration. No personal profile or Google account is required to start the dashboard. Google Calendar shows a connection prompt until configured; interactive OAuth requires an explicit `calendar_utils.get_calendar_service(authorize=True)` setup call. Install `google-api-python-client google-auth-httplib2 google-auth-oauthlib` for that connection. Calendar writes retain their existing human confirmation.

Private development can verify the entire export with `publish_sync.py --check`. It builds a disposable package, checks imports and privacy, starts the real HTTP server against empty isolated storage, and refuses external network/CLI execution or writes into the package. `--apply` runs the same gate before changing the public clone. Neither command pushes.

## MCP connection monitoring

Settings → **MCP connections** presents one collapsed row per MCP: status, expiry and the apps using it. Expand a row to retry checks, pause monitoring or set an expiry reminder. Client/profile differences and technical evidence stay inside the row. The monitor runs independently of the AI engine used to operate SHUKI; it also works with just one client installed.

Built-in discovery reads existing local configuration for Claude, Codex, Cursor and VS Code. JSON `mcpServers`, VS Code `servers` (including comments/trailing commas), and TOML `mcp_servers` are normalized into the same monitoring core. Configuration precedence and secrets remain with the original client. Configuration references: [Claude](https://code.claude.com/docs/en/mcp), [Codex](https://learn.chatgpt.com/docs/extend/mcp?surface=cli), [Cursor](https://prod.cursor.com/help/customization/mcp), [VS Code](https://code.visualstudio.com/docs/agent-customization/mcp-servers).

Other apps can supply their existing MCP configuration files through `SHUKI_MCP_CONFIG_FILES` (separate paths with `;` on Windows or `:` on macOS/Linux). Additional Claude profile directories can be selected through `SHUKI_CLAUDE_CONFIG_DIRS`; standard `CLAUDE_CONFIG_DIR` and `CODEX_HOME` are also respected. No SHUKI-specific MCP config file or duplicated credentials are required. Registered Python integrations may pass `(client_name, config_path)` entries to `inventory(extra_sources=...)`; new built-in JSON clients can be added through `JSON_CLIENTS` and `CLIENT_HELP`.

Checks use MCP initialization and tool discovery without calling tools. Google Calendar has a separate refresh-grant adapter; other providers' private OAuth stores and cloud-only connections may need checking in their app. Unknown expiry is shown as **Not provided**, and unsupported automatic checks as **Not checked**. Actual connection/authentication failures and approaching/passed expiry reminders generate deduplicated notifications. Monitoring state stays in the Git-excluded `runner_state/mcp-health.json`; tokens and raw provider errors are excluded from public status.

> 🎚 **このフォルダは B段・C段（ダッシュボード／定期ルーティン）用です。**
> A段（Obsidian ＋ Claude Code だけの個人wiki）で使う人は、**このフォルダを丸ごと無視して構いません** — clone しても、ここのスクリプトを起動しなければ何も動きません（常駐プロセス・インストール・バックグラウンド処理は一切なし）。3段の説明は [ルートの README](../README.md) の「🎚 どこまで使うか」の節を参照。

このリポジトリに同梱する配布用スクリプト。`vault_lint.py` は vault の**決定的QA**（LLM不使用・誤検出0%設計）で、frontmatter の構造・`status`・`date`・デッドリンクなど「明文化されたルール」だけを機械チェックする。

> なぜ同梱するか：「静かな故障の監視」というこのテンプレの核思想を、口だけでなく実装で提供するため。LLM に明文ルールのQAをやらせると誤検出が多く、正しいデータを「違反」と誤って直そうとする。だから明文ルールは決定的コードで、というのが方針（→ `CLAUDE.md` / `00_Intranet/AI運用ルール集（イントラ）/🔄 QAサイクル.md`）。

## vault_lint.py

### 依存
```bash
pip install pyyaml
```

### 実行
```bash
# vault ルートで
python scripts/vault_lint.py --vault .

# 別の場所から vault を指定
python scripts/vault_lint.py --vault /path/to/your-vault
```

- 出力先: `<vault>/99_System/qa/YYYY-MM-DD.md`（日付別・朝の orchestrator がトリアージ）
- `--vault` 省略時はカレントディレクトリを vault とみなす
- **Area は `05_Areas/*.md` のファイル名から動的に取得**する（`Areas.md`・`README.md`・`_example-*` は除外）。Area が1つも無ければ area チェックはスキップされる
- チェック対象外フォルダ: `.git` `.obsidian` `.claude` `08_Archive` `_Templates` `docs` `scripts` など（Templater 構文の誤検出を防ぐ）

### チェック項目
1. frontmatter 構造（`---` の開始・閉じ・1行潰れ・YAML実パース・重複キー）
2. 未クォート wikilink（`parent: [[X]]` は YAML で壊れる → `parent: "[[X]]"`）
3. `title` の存在（frontmatter を持つ全ファイルで必須。Obsidian 外への移行可搬性）
4. `area` 値が `05_Areas/` のいずれか（または空）
5. `status` 値がフォルダ別の許容セット内（`archived` は全DB共通で許容）
6. `date` / `created` の欠落・形式（`YYYY-MM-DD` 開始でない値は要対応）
7. 期間物の `date` は期間の最終日
8. デッドwikilink（参考情報・エラー扱いしない）

生成される `99_System/qa/` は `.gitignore` で除外され、公開リポジトリには入らない。

---

## news_fetch.py（購読フィードから重要な新着だけを拾う）

RSS/Atom を標準ライブラリだけで取得し、**既読との差分**を候補にして、`claude -p` には「どれが重要か」の判断だけをさせる。ダッシュボードの `/news` に表示される。

```bash
# 初回：購読フィードを作る
python scripts/news_fetch.py --init-feeds general
python scripts/news_fetch.py --init-feeds research --topic "graph neural network"   # arXiv検索

# 取得＋選定
python scripts/news_fetch.py
```

- 購読先と関心は `<vault>/99_System/news/feeds.json`（`interests` に「何を重要とみなすか」を書くほど選定が効く）
- **既読管理があるので毎日動かす必要はない** — 3日ぶりに実行すれば3日分がまとめて出る
- 新着0件なら claude を呼ばない（実行コストゼロ）
- **URL捏造の防止が設計の核**：AI が触れるのは「候補一覧のどの url を選ぶか」と一言の理由だけで、生成後に url が候補集合に実在するか機械検証し、無いものは破棄する。タイトル・出典・日付は候補側の値で復元するので、記事内容そのものの幻覚が構造的に起きない
- 研究用途の導入手順は [QUICKSTART-RESEARCH.md](../docs/QUICKSTART-RESEARCH.md) へ

---

## register-scheduled-tasks.ps1（Windows・自動実行をオンにする）

**Claude Code の定期実行タスクをワンコマンドで一括登録する**スクリプト。これを実行するまで、News 取得もインボックス振り分けもタスクディスパッチも**自動では動かない**（＝手動で `@orchestrator ...` を呼ぶ必要がある）。1回登録すれば vault が無人で回り始める。

### 実行（管理者権限の PowerShell）
```powershell
& "<リポ>\scripts\register-scheduled-tasks.ps1" -Vault "C:\path\to\your-vault"
```

主なパラメタ：

| パラメタ | 既定 | 用途 |
|---|---|---|
| `-Vault`（必須） | — | vault のルート |
| `-Workspace` | `<Vault>\..\vault-scripts` | `vault_lint.py` を置いた場所 |
| `-ClaudeExe` | `claude` | claude CLI のパス／コマンド名 |
| `-PythonExe` | `python` | Python 実行コマンド |
| `-LogDir` | `<Vault>\99_System\agent-runs` | 実行ログ出力先 |

登録されるタスク（`\Claude\` 配下・**失敗時リトライ 30分後・最大3回**付き）：

| タスク | スケジュール |
|---|---|
| Claude-NewsDigest | 毎日 7:20 |
| Claude-InboxSweep（haiku） | 日中 9/12/15/18/21時 |
| Claude-TaskDispatch | 毎日 12:30 |
| Claude-VaultLint | 毎日 0:05 |
| Claude-NightQA | 週2回（水・日）2:00 |
| Claude-KnowledgeEnrich | 週次 日曜 20:00 |

### 前提と注意
- **管理者権限**が必要（`\Claude\` へのタスク登録のため）。日本語を含むため PS1 は **UTF-8 BOM 付き**で保存されている（PowerShell 5.1 の文字化け対策）。
- タスクは `claude -p` を無人実行し、**Anthropic の課金・セッションを消費**する。事前に claude CLI がログイン済み・`.claude/settings.json` でツール許可済みであること。
- **まず1タスクだけ手動テスト**して動作確認するのがおすすめ：
  ```powershell
  Get-ScheduledTask -TaskPath '\Claude\'
  Start-ScheduledTask -TaskName 'Claude-InboxSweep' -TaskPath '\Claude\'
  ```
- 解除：`Get-ScheduledTask -TaskPath '\Claude\' | Unregister-ScheduledTask -Confirm:$false`

### macOS / Linux（cron）
同等の自動化は cron で。例（vault_lint を毎日 0:05）：
```
5 0 * * *  /usr/bin/python3 /path/to/vault_lint.py --vault /path/to/your-vault
20 7 * * *  cd /path/to/your-vault && /usr/bin/python3 scripts/news_fetch.py >> ~/claude-logs/news.log 2>&1
0 9-21/3 * * *  cd /path/to/your-vault && claude -p --model haiku "@orchestrator 01_Inbox/ の未処理ファイルを振り分け・プロパティ補完" >> ~/claude-logs/inbox.log 2>&1
```
