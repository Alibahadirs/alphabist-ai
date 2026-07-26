$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonExe = Join-Path $ProjectDir ".venv\Scripts\python.exe"
$ConfigFile = Join-Path $ProjectDir "data\daily_report_config.json"

if (-not (Test-Path $PythonExe)) { throw "Proje Python ortamı bulunamadı." }
if (-not (Test-Path $ConfigFile)) { throw "Önce configure_daily_report.py dosyasını çalıştırın." }

$Action = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument "-m app.daily_scan.runner" `
    -WorkingDirectory $ProjectDir
$Trigger = New-ScheduledTaskTrigger -Weekly -WeeksInterval 1 -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 7:00PM
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun -ExecutionTimeLimit (New-TimeSpan -Hours 2)
$WindowsUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$Principal = New-ScheduledTaskPrincipal -UserId $WindowsUser -LogonType Interactive -RunLevel Limited
$TaskName = "AlphaBIST AI Daily Report"
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Force | Out-Null
Write-Host "Görev hazır: hafta içi her gün 19:00. Bilgisayar kapalıysa açıldığında ilk fırsatta çalışır."
