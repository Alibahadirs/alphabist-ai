# Portföy Yöneticisi günlük sinyal uyarısı için Windows Görev Zamanlayıcı görevi oluşturur.
# Önce configure_daily_alert.py çalıştırılmış olmalıdır.
$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SharedVenvPython = Join-Path (Split-Path -Parent $ProjectDir) ".venv\Scripts\python.exe"
$ConfigFile = Join-Path $ProjectDir "data\daily_alert_config.json"

if (-not (Test-Path $SharedVenvPython)) { throw "Paylaşılan sanal ortam bulunamadı: $SharedVenvPython" }
if (-not (Test-Path $ConfigFile)) { throw "Önce configure_daily_alert.py dosyasını çalıştırın." }

$Action = New-ScheduledTaskAction `
    -Execute $SharedVenvPython `
    -Argument "-m pm.alerts.runner" `
    -WorkingDirectory $ProjectDir
$Trigger = New-ScheduledTaskTrigger -Daily -At 7:30PM
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun -ExecutionTimeLimit (New-TimeSpan -Hours 1)
$WindowsUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$Principal = New-ScheduledTaskPrincipal -UserId $WindowsUser -LogonType Interactive -RunLevel Limited
$TaskName = "Portfoy Yoneticisi Gunluk Uyari"
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Force | Out-Null
Write-Host "Görev hazır: her gün 19:30. Bilgisayar kapalıysa açıldığında ilk fırsatta çalışır."
Write-Host "Hafta sonları BIST kapalı olduğu için otomatik atlanır (--force ile zorlanabilir)."
