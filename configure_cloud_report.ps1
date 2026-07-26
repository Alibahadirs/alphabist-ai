$ErrorActionPreference = "Stop"
$Repository = "Alibahadirs/alphabist-ai"
$Sender = "wrapplicationn@gmail.com"
$Recipient = "akkayatokat@gmail.com"

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { throw "GitHub aracı bulunamadı." }
$SecurePassword = Read-Host "Yeni Gmail hesabının 16 karakterlik uygulama parolası" -AsSecureString
$Pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecurePassword)
try {
    $PlainPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($Pointer).Replace(" ", "")
    if ($PlainPassword.Length -ne 16) { throw "Uygulama parolası 16 karakter olmalıdır." }
    $Sender | gh secret set ALPHABIST_GMAIL_SENDER --repo $Repository
    $Recipient | gh secret set ALPHABIST_REPORT_RECIPIENT --repo $Repository
    $PlainPassword | gh secret set ALPHABIST_GMAIL_APP_PASSWORD --repo $Repository
}
finally {
    if ($Pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Pointer) }
    $PlainPassword = $null
    $SecurePassword = $null
}
Write-Host "Bulut e-posta ayarları GitHub Secrets alanına kaydedildi."
