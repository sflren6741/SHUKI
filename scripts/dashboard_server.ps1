# dashboard_server.ps1 — ダッシュボードサーバーの起動・生存監視ガード（冪等・多重起動しない）
# 呼び出し元: .vscode/tasks.json の "dashboard-server"（folderOpen 自動実行）＋
#            Task Scheduler「Claude-DashboardAutoStart」（ログオン時＋15分おき）
#
# 2026-08-16: 生存判定を TCP接続可否 → 実際に HTTP 200 が返るか に強化。
# 旧版はポートが開いてさえいれば「動いている」と判定していたため、プロセスは生きているが
# ホーム(/)が例外で500を返し続ける状態（設定ドリフトによる KeyError）を検知できず、
# ユーザーが外出中に気づくまで誰も直せなかった実障害があった（📚 教訓集 2026-08-16 参照）。
param(
    [switch]$Restart,
    [switch]$Defer,
    [switch]$CheckOnly,
    [switch]$Status,
    [int]$ExpectedProcessId = 0
)

$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ScriptDir = $PSScriptRoot
$Port = 8765
$Url  = "http://127.0.0.1:$Port/"
$PythonExe = Join-Path $ScriptDir ".venv\Scripts\python.exe"
$ServerPath = Join-Path $ScriptDir 'dashboard_server.py'
# The runner state folder lives outside the code tree; ask the same resolver the Python code uses.
function Resolve-StorePath([string]$Key, [string]$Fallback) {
    try {
        $resolved = & $PythonExe (Join-Path $ScriptDir 'shuki_paths.py') store $Key 2>$null
        if ($LASTEXITCODE -eq 0 -and $resolved) { return ([string]($resolved | Select-Object -First 1)).Trim() }
    } catch {}
    return $Fallback
}
$RestartState = Join-Path (Resolve-StorePath 'runner/state' (Join-Path $ScriptDir 'runner_state')) 'dashboard-restart.json'

function Get-DashboardOwner {
    $owners = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique)
    if ($owners.Count -ne 1) { throw 'Expected exactly one dashboard listener; no process was stopped.' }
    $server = Get-CimInstance Win32_Process -Filter "ProcessId=$($owners[0])"
    $pathPattern = '(?i)(?:^|\s)"?' + [regex]::Escape($ServerPath) + '"?(?:\s|$)'
    if (-not $server -or $server.Name -notmatch '^python(?:w|3\.12)?\.exe$' -or
        $server.CommandLine -notmatch $pathPattern -or
        ($ExpectedProcessId -gt 0 -and $server.ProcessId -ne $ExpectedProcessId)) {
        throw 'Port 8765 is not owned by the expected SHUKI server; no process was stopped.'
    }
    return $server
}

function Write-RestartState {
    param([string]$Phase, [string]$Detail, [int]$PreviousId, [int]$CurrentId = 0)
    $state = @{status=$Phase; detail=$Detail; previous_process_id=$PreviousId;
        current_process_id=$CurrentId; updated=(Get-Date).ToUniversalTime().ToString('o')}
    [void][System.IO.Directory]::CreateDirectory((Split-Path $RestartState -Parent))
    $temporary = $RestartState + ".$PID.tmp"
    [System.IO.File]::WriteAllText($temporary, ($state | ConvertTo-Json), [System.Text.UTF8Encoding]::new($false))
    Move-Item -LiteralPath $temporary -Destination $RestartState -Force
}

function Write-RestartNotice {
    param([string]$Phase, [string]$Detail, [int]$PreviousId)
    # Local dashboard notice only: never send ntfy/email from the restart worker.
    # The machine zone may live outside the vault (Phase B); ask the shared resolver.
    $systemPath = (& $PythonExe -c 'import shuki_paths; print(shuki_paths.system_dir())').Trim()
    if (-not $systemPath) { throw 'Could not resolve the machine zone for the restart result.' }
    $inbox = Join-Path $systemPath 'review-inbox'
    [void][System.IO.Directory]::CreateDirectory($inbox)
    $noticePath = Join-Path $inbox ("notice-dashboard-restart-$PreviousId.json")
    $notice = @{source='system'; kind='Notification';
        notification=$(if ($Phase -eq 'done') {'important_result'} else {'blocker'});
        title=$(if ($Phase -eq 'done') {'SHUKI server restarted'} else {'SHUKI restart stopped'});
        summary=$Detail; ts=[DateTimeOffset]::UtcNow.ToUnixTimeSeconds();
        push_pending=$false; push_attempts=0}
    [System.IO.File]::WriteAllText($noticePath, ($notice | ConvertTo-Json), [System.Text.UTF8Encoding]::new($false))
}

function Invoke-DashboardRestart {
    if (-not (Test-Path -LiteralPath $PythonExe) -or -not (Test-Path -LiteralPath $ServerPath)) {
        throw 'SHUKI server or project interpreter is missing; no process was stopped.'
    }
    & $PythonExe --version | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Project interpreter check failed; no process was stopped.' }
    $original = Get-DashboardOwner
    if ($CheckOnly) {
        @{status='ready'; process_id=$original.ProcessId; healthy=(Test-DashboardHealthy)} |
            ConvertTo-Json -Compress | Write-Output
        return
    }
    if ($Defer) {
        $powershellExe = Join-Path $PSHOME 'powershell.exe'
        Start-Process -FilePath $powershellExe -ArgumentList @('-NoProfile', '-File',
            ('"' + $PSCommandPath + '"'), '-Restart', '-ExpectedProcessId', $original.ProcessId) `
            -WorkingDirectory $ScriptDir -WindowStyle Hidden | Out-Null
        Write-Output 'Restart worker launched; it waits for active work and verifies HTTP before reporting success.'
        return
    }
    $restartMutex = [System.Threading.Mutex]::new($false, 'Local\SHUKI-DashboardRestart')
    $hasLock = $false
    try {
        $hasLock = $restartMutex.WaitOne(0)
        if (-not $hasLock) { throw 'A dashboard restart worker is already active.' }
        Write-RestartState 'waiting' 'Waiting for workers to finish and 30 seconds of idle time.' $original.ProcessId
        $seenJobs = [System.Collections.Generic.HashSet[string]]::new()
        $idleSince = $null
        $deadline = (Get-Date).AddHours(1)
        while ((Get-Date) -lt $deadline) {
            $current = Get-DashboardOwner
            if ($current.ProcessId -ne $original.ProcessId -or $current.CreationDate -ne $original.CreationDate) {
                throw 'Original server identity changed; no process was stopped.'
            }
            $children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$($original.ProcessId)" |
                Where-Object { $_.Name -ne 'conhost.exe' -and $_.CommandLine -notmatch 'stt_server\.py' })
            $recent = (Invoke-WebRequest ($Url + 'log') -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop).Content
            foreach ($jobMatch in [regex]::Matches($recent, '(?:voice-|work-|journal-)?\d{15,}')) {
                [void]$seenJobs.Add($jobMatch.Value)
            }
            $busy = $children.Count -gt 0
            foreach ($jobId in @($seenJobs)) {
                try { $job = Invoke-RestMethod ($Url + 'job?id=' + $jobId) -TimeoutSec 5 -ErrorAction Stop }
                catch {
                    if ($_.Exception.Response -and [int]$_.Exception.Response.StatusCode -eq 404) {
                        [void]$seenJobs.Remove($jobId)
                        continue
                    }
                    throw
                }
                if ($job.status -in @('running', 'waiting')) { $busy = $true }
            }
            if ($busy) { $idleSince = $null }
            elseif (-not $idleSince) { $idleSince = Get-Date }
            elseif (((Get-Date) - $idleSince).TotalSeconds -ge 30) { break }
            Start-Sleep -Seconds 5
        }
        if (-not $idleSince -or ((Get-Date) - $idleSince).TotalSeconds -lt 30) {
            throw 'Dashboard did not become idle within one hour; no process was stopped.'
        }
        # Recheck identity and children immediately before the explicitly requested restart.
        $current = Get-DashboardOwner
        if ($current.ProcessId -ne $original.ProcessId -or $current.CreationDate -ne $original.CreationDate) {
            throw 'Original server identity changed; no process was stopped.'
        }
        $children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$($original.ProcessId)" |
            Where-Object { $_.Name -ne 'conhost.exe' -and $_.CommandLine -notmatch 'stt_server\.py' })
        if ($children.Count -gt 0) { throw 'New dashboard work started; no process was stopped.' }
        Write-RestartState 'restarting' 'Restarting the verified, idle SHUKI server.' $original.ProcessId
        Stop-Process -Id $original.ProcessId -Confirm:$false -ErrorAction Stop
        Start-Sleep -Seconds 2
        Start-Process -FilePath $PythonExe -ArgumentList ('"' + $ServerPath + '"') `
            -WorkingDirectory $ScriptDir -WindowStyle Hidden | Out-Null
        Start-Sleep -Seconds 5
        if (-not (Test-DashboardHealthy)) {
            Start-Sleep -Seconds 5
            if (-not (Test-DashboardHealthy)) { throw 'Replacement dashboard did not return HTTP 200.' }
        }
        $ExpectedProcessId = 0
        $replacement = Get-DashboardOwner
        if ($replacement.ProcessId -eq $original.ProcessId) { throw 'Dashboard process did not change.' }
        $detail = "Restart verified: HTTP 200 at $Url; process $($original.ProcessId) replaced by $($replacement.ProcessId)."
        Write-RestartState 'done' $detail $original.ProcessId $replacement.ProcessId
        Write-RestartNotice 'done' $detail $original.ProcessId
        Write-Output $detail
    } catch {
        if ($hasLock) {
            Write-RestartState 'failed' $_.Exception.Message $original.ProcessId
            Write-RestartNotice 'failed' $_.Exception.Message $original.ProcessId
        }
        throw
    } finally {
        if ($hasLock) { $restartMutex.ReleaseMutex() }
        $restartMutex.Dispose()
    }
}

function Test-DashboardHealthy {
    try {
        $r = Invoke-WebRequest -Uri $Url -TimeoutSec 5 -UseBasicParsing
        return $r.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Send-FailureAlert {
    param([string]$Detail)
    # Normal recovery alerts use the selected SHUKI channel and durable outbox.
    # Keep the legacy fallback only when the project interpreter itself is missing.
    if (Test-Path -LiteralPath $PythonExe) {
        $pushHelper = Join-Path $ScriptDir 'shuki_webpush.py'
        try { & $PythonExe $pushHelper --alert $Detail | Out-Null } catch {}
        return
    }
    # 通知は shuki_paths.json の ntfy_topic 設定時のみ（未設定なら何もせず戻る＝機能OFFで壊れない）。
    # 失敗してもこのスクリプト自体の成否には影響させない。
    try {
        # 2026-09-28: 設定は公開リポジトリの作業ツリー外（隣の shuki-secrets/）へ移した。
        # 旧位置にもフォールバックする（移行前の環境でも壊れないように）。
        $cfgPath = Join-Path (Split-Path $ScriptDir -Parent) "shuki-secrets\shuki_paths.json"
        if (-not (Test-Path $cfgPath)) { $cfgPath = Join-Path $ScriptDir "shuki_paths.json" }
        if (-not (Test-Path $cfgPath)) { return }
        $cfg = Get-Content $cfgPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $topic = $cfg.ntfy_topic
        if (-not $topic) { return }
        $payload = @{
            topic    = $topic
            title    = "SHUKIダッシュボードが復旧できません"
            message  = $Detail
            priority = 4
        } | ConvertTo-Json -Compress
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($payload)
        Invoke-RestMethod -Uri "https://ntfy.sh/" -Method POST -Body $bytes -ContentType "application/json; charset=utf-8" | Out-Null
    } catch {}
}

if ($Status) {
    if (Test-Path -LiteralPath $RestartState) { Get-Content -LiteralPath $RestartState -Raw -Encoding UTF8 }
    else { Write-Output '{"status":"not_requested"}' }
    exit 0
}
if ($Restart) {
    Invoke-DashboardRestart
    exit 0
}
if ($Defer -or $CheckOnly -or $ExpectedProcessId -gt 0) { throw 'Restart options require -Restart.' }
if (Test-DashboardHealthy) { exit 0 }

# 一度失敗しただけでは再起動しない（Task Scheduler実行時のごく短い一時的な詰まりで、生きている
# プロセス・実行中のジョブを無駄に巻き込んで殺すのを避ける）。数秒空けてもう一度失敗したら
# 「壊れている」と判定して再起動に進む。
Start-Sleep -Seconds 3
if (Test-DashboardHealthy) { exit 0 }

# 不健全＝①未起動 ②プロセスは生きているが応答が壊れている、のどちらか。
# ②の場合は既存プロセスがポートを掴んだままだと新規起動が「already running」で即終了するだけで
# 直らないため、ポートの所有プロセスを先に止めてから起動し直す。
$existing = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($existing) {
    foreach ($ownerPid in ($existing.OwningProcess | Sort-Object -Unique)) {
        try { Stop-Process -Id $ownerPid -Force -Confirm:$false -ErrorAction Stop } catch {}
    }
    Start-Sleep -Milliseconds 800
}

if (-not (Test-Path -LiteralPath $PythonExe)) {
    Write-Output "SHUKI project interpreter not found: $PythonExe"
    Send-FailureAlert -Detail "SHUKI dashboard restart skipped because the project interpreter was not found: $PythonExe"
    exit 1
}
Start-Process -FilePath $PythonExe -ArgumentList "`"$ScriptDir\dashboard_server.py`"" -WorkingDirectory $ScriptDir -WindowStyle Hidden

for ($i = 0; $i -lt 10; $i++) {
    Start-Sleep -Milliseconds 500
    if (Test-DashboardHealthy) { exit 0 }
}

$msg = "起動/再起動を試みましたが http://127.0.0.1:$Port/ が200を返しません。PCで直接確認してください。"
Write-Output "dashboard server unhealthy after restart attempt (port $Port)"
Send-FailureAlert -Detail $msg
exit 1
