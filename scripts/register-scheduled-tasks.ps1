<#
.SYNOPSIS
  Claude Code の定期実行タスクを Windows Task Scheduler にワンコマンド登録する。

.DESCRIPTION
  News 取得・インボックス振り分け・タスクディスパッチ便・決定的QA（vault_lint）・
  夜間QA・ナレッジ週次メンテを、失敗時リトライ付きで `\Claude\` フォルダにまとめて登録する。
  これを1回実行すれば、以後 vault が無人で回り始める。

  ⚠️ これらのタスクは `claude -p` を無人で叩く＝Anthropic の課金・セッションを消費する。
     事前に (1) claude CLI がログイン済み (2) `.claude/settings.json` で必要ツールを許可済み
     であること。登録はオプトイン（あなたが意図して実行する）。

.PARAMETER Vault
  vault のルート（例: C:\Users\you\my-vault）。必須。

.PARAMETER Workspace
  vault-scripts（vault_lint.py 等）を置くフォルダ。省略時は <Vault>\..\vault-scripts。

.PARAMETER ClaudeExe
  claude CLI のパスまたはコマンド名（省略時 "claude"）。

.PARAMETER PythonExe
  python の実行コマンド（省略時 "python"）。

.PARAMETER LogDir
  実行ログの出力先（省略時 <Vault>\99_System\agent-runs）。

.EXAMPLE
  # 管理者権限の PowerShell で
  .\register-scheduled-tasks.ps1 -Vault "C:\Users\you\my-vault"

.NOTES
  日本語を含むため UTF-8 BOM 付きで保存すること（PowerShell 5.1 の文字化け対策）。
#>
param(
  [Parameter(Mandatory = $true)][string]$Vault,
  [string]$Workspace = "",
  [string]$ClaudeExe = "claude",
  [string]$PythonExe = "python",
  [string]$LogDir = ""
)

$ErrorActionPreference = "Stop"

# --- 前提チェック ---
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
  Write-Warning "管理者権限がありません。`\Claude\` へのタスク登録には管理者 PowerShell が必要です。"
  Write-Host "対処: PowerShell を「管理者として実行」で開き直してから、もう一度このスクリプトを実行してください。"
  exit 1
}

$Vault = (Resolve-Path $Vault).Path
if (-not (Test-Path (Join-Path $Vault "CLAUDE.md"))) {
  Write-Warning "指定パスに CLAUDE.md が見つかりません（vault のルートを -Vault に指定してください）: $Vault"
}
if (-not $Workspace) { $Workspace = Join-Path (Split-Path $Vault -Parent) "vault-scripts" }
if (-not $LogDir)    { $LogDir    = Join-Path $Vault "99_System\agent-runs" }
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$TaskPath = "\Claude\"

# 失敗時リトライ（30分後・最大3回）＋ 起動漏れを取り返す設定
$settings = New-ScheduledTaskSettingsSet `
  -RestartCount 3 `
  -RestartInterval (New-TimeSpan -Minutes 30) `
  -StartWhenAvailable `
  -DontStopOnIdleEnd `
  -ExecutionTimeLimit (New-TimeSpan -Hours 1)

# 現在ユーザーとしてログオン中に実行（無人ログオフ実行が要るなら -RunLevel/資格情報を各自で調整）
$principal = New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive

function Register-ClaudeTask {
  param(
    [string]$Name,
    [object[]]$Triggers,
    [string]$Command,   # powershell -Command に渡す本体
    [string]$Description
  )
  $arg = "-NoProfile -ExecutionPolicy Bypass -Command `"$Command`""
  $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $arg
  Register-ScheduledTask -TaskName $Name -TaskPath $TaskPath `
    -Trigger $Triggers -Action $action -Settings $settings -Principal $principal `
    -Description $Description -Force | Out-Null
  Write-Host ("  [OK] {0}" -f $Name)
}

# claude を叩く本体（vault へ移動 → claude -p → ログ追記）
function Claude-Command {
  param([string]$Prompt, [string]$LogName, [string]$ModelArg = "")
  $log = Join-Path $LogDir ("{0}_{1}.log" -f $LogName, (Get-Date -Format "yyyy-MM-dd"))
  $model = if ($ModelArg) { " $ModelArg" } else { "" }
  return "Set-Location '$Vault'; & '$ClaudeExe' -p$model '$Prompt' *>> '$log'"
}

Write-Host "Claude スケジュールタスクを登録します -> $TaskPath"
Write-Host ("  Vault    : {0}" -f $Vault)
Write-Host ("  Workspace: {0}" -f $Workspace)
Write-Host ""

# 1) News 取得（毎日 7:20）。購読フィードは 99_System/news/feeds.json（docs/QUICKSTART-RESEARCH.md §4）
$newsLog = Join-Path $LogDir ("news_fetch_{0}.log" -f (Get-Date -Format "yyyy-MM-dd"))
$newsScript = Join-Path $Vault "scripts\news_fetch.py"
Register-ClaudeTask -Name "Claude-NewsDigest" `
  -Triggers (New-ScheduledTaskTrigger -Daily -At 7:20am) `
  -Command "Set-Location '$Vault'; & '$PythonExe' '$newsScript' *>> '$newsLog'" `
  -Description "購読フィードの新着から重要なものを Claude が選び、ダッシュボードの /news に出す"

# 2) インボックス振り分け（日中 3時間おき＝9/12/15/18/21・定型なので haiku）
$sweepTriggers = @(9,12,15,18,21) | ForEach-Object {
  New-ScheduledTaskTrigger -Daily -At ([datetime]::Today.AddHours($_))
}
Register-ClaudeTask -Name "Claude-InboxSweep" `
  -Triggers $sweepTriggers `
  -Command (Claude-Command "@orchestrator 01_Inbox/ の未処理ファイルを振り分け・プロパティ補完" "inbox" "--model haiku") `
  -Description "インボックスの未処理(status:new)を振り分け・プロパティ補完（軽量モデル）"

# 3) タスクディスパッチ便（毎日 12:30）
Register-ClaudeTask -Name "Claude-TaskDispatch" `
  -Triggers (New-ScheduledTaskTrigger -Daily -At 12:30pm) `
  -Command (Claude-Command "@orchestrator タスクディスパッチ便を実行（§🚚）" "dispatch") `
  -Description "ai_judgment_ok の todo/in-progress タスクを担当エージェントに実行させる社内便（最大3件/便）"

# 4) 決定的QA vault_lint（毎日 0:05・LLM不使用）
$lintLog = Join-Path $LogDir ("vault-lint_{0}.log" -f (Get-Date -Format "yyyy-MM-dd"))
$lintScript = Join-Path $Workspace "vault_lint.py"
Register-ClaudeTask -Name "Claude-VaultLint" `
  -Triggers (New-ScheduledTaskTrigger -Daily -At 0:05am) `
  -Command "& '$PythonExe' '$lintScript' --vault '$Vault' *>> '$lintLog'" `
  -Description "vault_lint.py で frontmatter/status/date/デッドリンクを決定的チェックし 99_System/qa へ出力"

# 5) 夜間QA（週2回・水/日 2:00・監視の自己肥大を避けるため毎日にしない）
Register-ClaudeTask -Name "Claude-NightQA" `
  -Triggers (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Wednesday,Sunday -At 2:00am) `
  -Command (Claude-Command "@infrastructure エージェント稼働ログを確認してサマリーを更新" "infrastructure") `
  -Description "稼働ログ(.log)を集計し稼働サマリーを更新（日曜は運用改善スキャンも）"

# 6) ナレッジ週次メンテ（毎週日曜 20:00）
Register-ClaudeTask -Name "Claude-KnowledgeEnrich" `
  -Triggers (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 8:00pm) `
  -Command (Claude-Command "@knowledge メンテナンスモードで実行" "knowledge") `
  -Description "既存ナレッジの wikilink 整備・陳腐化検出"

Write-Host ""
Write-Host "完了。登録済みタスクの確認:  Get-ScheduledTask -TaskPath '\Claude\'"
Write-Host "解除したいとき:              Get-ScheduledTask -TaskPath '\Claude\' | Unregister-ScheduledTask -Confirm:`$false"
Write-Host ""
Write-Warning "これらは claude -p を無人実行し課金・セッションを消費します。まず1タスクだけ手動テスト(Start-ScheduledTask)して動作を確認してください。"
