# Scripts

These scripts run the local dashboard, fetch news and check vault structure. If you use only Obsidian and Claude Code, you can leave this folder alone. See the [main README](../README.en.md) for an overview.

## Dashboard

The public dashboard includes AI chat, tasks, a calendar, news and decision cards. Home opens the task board with the shared chat panel. Decision cards let you approve a request or provide missing information. The author's additional plugins are not included.

Use Python 3.11 or newer. Set `SHUKI_VAULT` to your vault's absolute path, then run the server from the repository root:

```powershell
$env:SHUKI_VAULT = (Get-Location).Path
python scripts/dashboard_server.py
```

Open <http://127.0.0.1:8765/>. If the vault is elsewhere, replace `(Get-Location).Path` with its absolute path. On macOS or Linux, set the same environment variable with your shell's `export` command.

`SHUKI_DATA_DIR` optionally sets an absolute directory for runtime data outside the code tree. Fresh installations create their stores there. Existing installations keep populated legacy stores until an explicit migration. Decision records and response history belong to those runtime stores, not the public package.

The core uses the Python standard library and can start without a personal profile or Google account. AI chat needs the selected Claude Code or Codex CLI installed and configured. To connect Google Calendar, install:

```sh
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

Complete the OAuth setup with an explicit `calendar_utils.get_calendar_service(authorize=True)` call. Until then, the calendar shows a connection prompt. Calendar writes require human confirmation.

## MCP connection monitoring

**Settings → MCP connections** lists connection status, expiry and the apps using each connection. Expand a row to retry a check, pause monitoring or set an expiry reminder. Monitoring works independently of the AI engine selected in SHUKI.

Discovery reads existing local configuration for Claude, Codex, Cursor and VS Code. It understands JSON `mcpServers`, VS Code `servers` with comments or trailing commas, and TOML `mcp_servers`. Credentials and configuration precedence stay with the original client. See the configuration docs for [Claude](https://code.claude.com/docs/en/mcp), [Codex](https://learn.chatgpt.com/docs/extend/mcp?surface=cli), [Cursor](https://prod.cursor.com/help/customization/mcp) and [VS Code](https://code.visualstudio.com/docs/agent-customization/mcp-servers).

Other apps can provide configuration paths through `SHUKI_MCP_CONFIG_FILES`, separated by `;` on Windows or `:` on macOS and Linux. `SHUKI_CLAUDE_CONFIG_DIRS` selects additional Claude profile directories. Standard `CLAUDE_CONFIG_DIR` and `CODEX_HOME` settings are also respected.

Checks initialize an MCP connection and discover tools without calling them. Google Calendar uses a separate refresh-grant check. Some private OAuth stores and cloud-only connections must be checked in their own app. Missing expiry appears as **Not provided**; unsupported checks appear as **Not checked**. Failures and expiry reminders produce deduplicated notifications. Tokens and raw provider errors are excluded from public status.

For Python integrations, `inventory(extra_sources=...)` accepts `(client_name, config_path)` entries. Built-in JSON clients are defined by `JSON_CLIENTS` and `CLIENT_HELP`.

## Vault checks

`vault_lint.py` checks explicitly defined rules without using an LLM. It checks frontmatter structure, required fields, permitted values and links; it does not judge the content of a note.

Install its dependency and run it from the repository root:

```sh
pip install pyyaml
python scripts/vault_lint.py --vault .
```

Use `--vault /path/to/your-vault` to check another vault. Without `--vault`, the current directory is used.

Checks cover:

- Frontmatter delimiters, YAML parsing and duplicate keys
- Quoted wikilinks in properties such as `parent`
- Required `title`, `date` and `created` fields
- Area names and permitted status values
- Dates for records covering a period
- Unresolved wikilinks, reported as reference information

Area names come from the notes in `05_Areas/`, excluding hub, README and example files. If there are no area notes, that check is skipped. Code, configuration, templates and archive folders are excluded from the scan.

Reports are written to `07_Logs/レポート/QA/YYYY-MM-DD.md` in the vault. Generated reports are not part of the public package.

## News feeds

`news_fetch.py` reads RSS and Atom feeds, removes previously seen URLs and asks Claude Code to select relevant new articles. The results appear at `/news`.

```sh
python scripts/news_fetch.py --init-feeds general
python scripts/news_fetch.py --init-feeds research --topic "graph neural network"
python scripts/news_fetch.py
```

Edit subscriptions and interests through `/news/sources` or the runtime `feeds.json` file. Seen-URL tracking avoids selecting the same articles again. When there are no new feed candidates, the article-selection call is skipped.

Selected URLs are checked against the fetched candidates. Titles, sources and dates are taken from feed data. This catches URLs invented by the selector; it does not verify the accuracy of the source article or the AI's explanation.

See the [research quick start](../docs/en/QUICKSTART-RESEARCH.md) for a setup focused on papers and tasks.

## Scheduled jobs

Cloning the repository does not register scheduled jobs. Configure them after checking that the corresponding commands work manually. Unattended Claude Code jobs consume the account's usage allowance.

On Windows, `register-scheduled-tasks.ps1` registers jobs under `\Claude\`. Run it in an administrator PowerShell session:

```powershell
& "C:\path\to\my-vault\scripts\register-scheduled-tasks.ps1" -Vault "C:\path\to\my-vault"
```

| Parameter | Default | Purpose |
|---|---|---|
| `-Vault` | Required | Vault root |
| `-Workspace` | `<Vault>\..\vault-scripts` | Location of `vault_lint.py` |
| `-ClaudeExe` | `claude` | Claude Code command or executable |
| `-PythonExe` | `python` | Python executable |
| `-LogDir` | `<Vault>\99_System\agent-runs` | Execution logs |

Check these defaults against your installation and pass explicit paths where needed. The script is saved with a UTF-8 BOM for Windows PowerShell compatibility.

| Job | Schedule |
|---|---|
| Claude-NewsDigest | Daily at 07:20 |
| Claude-InboxSweep | 09:00, 12:00, 15:00, 18:00 and 21:00 |
| Claude-TaskDispatch | Daily at 12:30 |
| Claude-VaultLint | Daily at 00:05 |
| Claude-NightQA | Wednesday and Sunday at 02:00 |
| Claude-KnowledgeEnrich | Sunday at 20:00 |

The CLI must already be signed in, with the required tools permitted. Test one job before relying on the schedule:

```powershell
Get-ScheduledTask -TaskPath '\Claude\'
Start-ScheduledTask -TaskName 'Claude-InboxSweep' -TaskPath '\Claude\'
```

On macOS or Linux, configure the corresponding commands through cron. See the [automation guide](../docs/en/AUTOMATION.md) for the broader workflow.

## Public export checks

Private development uses `publish_sync.py --check` to verify a disposable export. The check covers imports, privacy patterns and server startup with isolated empty storage; it blocks external network calls, CLI execution and writes into packaged code.

`--apply` runs the same checks before updating the public clone. It does not push to GitHub.
