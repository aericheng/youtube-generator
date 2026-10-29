# Registers the Windows Task Scheduler job for the weekly YouTube report:
#   LofiWeeklyReport - every Monday 08:40, wscript hidden launcher -> run_weekly.cmd
#                      -> scripts\weekly_report.py (posts to Discord, writes data\last-success-weekly)
#
# Usage (after the one-time OAuth consent, see README "Weekly report"):
#   powershell -ExecutionPolicy Bypass -File scripts\register-weekly.ps1
#
# Pure ASCII (parsed by Windows PowerShell 5.1). Modelled on lab-slack-watch
# scripts\register-tasks.ps1. NOTE: this only registers the task when you run it.

$ErrorActionPreference = "Stop"

$repoRoot = "C:\Users\user\Desktop\dev\youtube generator"
$hiddenVbs = Join-Path $repoRoot "run_weekly_hidden.vbs"
$taskName = "LofiWeeklyReport"

$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Removing existing task: $taskName"
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

$action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$hiddenVbs`"" -WorkingDirectory $repoRoot
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At "08:40"
$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 15) `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask `
    -TaskName $taskName `
    -Description "Weekly YouTube channel report to Discord, Mondays 08:40" `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal | Out-Null

Write-Host "Registered task: $taskName"
Write-Host "Verify with: Get-ScheduledTask -TaskName $taskName"
