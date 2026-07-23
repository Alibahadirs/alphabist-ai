$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$RequirementsPath = Join-Path $ProjectRoot "requirements.txt"
$RequirementsMarker = Join-Path $ProjectRoot ".venv\.requirements.sha256"

if (-not (Test-Path $VenvPython)) {
    $Launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($null -ne $Launcher) {
        & py -m venv (Join-Path $ProjectRoot ".venv")
    }
    else {
        $Launcher = Get-Command python -ErrorAction SilentlyContinue
        if ($null -eq $Launcher) {
            throw "Python bulunamadı. Python 3.11 veya üstünü kurun."
        }
        & python -m venv (Join-Path $ProjectRoot ".venv")
    }
}

$RequirementsHash = (Get-FileHash $RequirementsPath -Algorithm SHA256).Hash
$StoredHash = if (Test-Path $RequirementsMarker) {
    (Get-Content $RequirementsMarker -Raw).Trim()
}
else {
    ""
}

$DependenciesReady = $false
if ($StoredHash -eq $RequirementsHash) {
    & $VenvPython -c "import streamlit, pandas, numpy, pydantic, yfinance, pypdf, ta"
    $DependenciesReady = $LASTEXITCODE -eq 0
}

if (-not $DependenciesReady) {
    Write-Host "AlphaBIST bağımlılıkları hazırlanıyor..."
    & $VenvPython -m pip install --upgrade pip
    & $VenvPython -m pip install -r $RequirementsPath
    if ($LASTEXITCODE -ne 0) {
        throw "Python bağımlılıkları kurulamadı."
    }
    Set-Content -Path $RequirementsMarker -Value $RequirementsHash
}

& $VenvPython -m app.core.preflight
if ($LASTEXITCODE -ne 0) {
    throw "Sistem ön kontrolü başarısız oldu."
}

try {
    $Health = Invoke-WebRequest `
        -Uri "http://localhost:8501/_stcore/health" `
        -UseBasicParsing `
        -TimeoutSec 2
    if ($Health.StatusCode -eq 200 -and $Health.Content.Trim() -eq "ok") {
        Write-Host "AlphaBIST AI zaten çalışıyor: http://localhost:8501"
        exit 0
    }
}
catch {
    # Port boşsa uygulama aşağıda başlatılır.
}

Write-Host "AlphaBIST AI başlatılıyor: http://localhost:8501"
& $VenvPython -m streamlit run main.py --server.headless true
