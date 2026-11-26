# sign_exe.ps1
# Creates a self-signed code-signing certificate (if it doesn't already exist),
# then uses it to sign FBRNotificationMonitor.exe.
# This removes the "Unknown Publisher" warning in the Windows installer UAC prompt.
# NOTE: Windows SmartScreen may still warn on first run because self-signed certs
# are not trusted by a public CA. The only way to fully suppress SmartScreen is
# to buy a certificate from a trusted CA (e.g. DigiCert, Sectigo).

$certSubject  = "CN=FBR Notification Monitor, O=Muhammad Wasim, E=mwasimmit@gmail.com"
$certStore    = "Cert:\CurrentUser\My"
$exePath      = "$PSScriptRoot\dist\FBRNotificationMonitor.exe"

# ── Step 1: Find or create a self-signed code-signing certificate ──────────
$cert = Get-ChildItem $certStore -CodeSigningCert |
        Where-Object { $_.Subject -eq $certSubject } |
        Select-Object -First 1

if (-not $cert) {
    Write-Host "Creating self-signed code-signing certificate..." -ForegroundColor Cyan
    $cert = New-SelfSignedCertificate `
        -Subject          $certSubject `
        -CertStoreLocation $certStore `
        -KeyUsage         DigitalSignature `
        -Type             CodeSigningCert `
        -NotAfter         (Get-Date).AddYears(5) `
        -HashAlgorithm    SHA256
    Write-Host "Certificate created: $($cert.Thumbprint)" -ForegroundColor Green
} else {
    Write-Host "Using existing certificate: $($cert.Thumbprint)" -ForegroundColor Yellow
}

# ── Step 2: Trust the cert locally (add to Trusted Root) ──────────────────
$root = Get-ChildItem "Cert:\LocalMachine\Root" |
        Where-Object { $_.Thumbprint -eq $cert.Thumbprint } |
        Select-Object -First 1

if (-not $root) {
    Write-Host "Adding certificate to Trusted Root (requires elevation)..." -ForegroundColor Cyan
    try {
        $store = New-Object System.Security.Cryptography.X509Certificates.X509Store("Root","LocalMachine")
        $store.Open("ReadWrite")
        $store.Add($cert)
        $store.Close()
        Write-Host "Certificate added to Trusted Root." -ForegroundColor Green
    } catch {
        Write-Warning "Could not add to Trusted Root (run as Administrator to do this). The 'Unknown Publisher' warning may still appear."
    }
}

# ── Step 3: Sign the .exe ─────────────────────────────────────────────────
if (-not (Test-Path $exePath)) {
    Write-Error "EXE not found at: $exePath"
    exit 1
}

Write-Host "Signing $exePath ..." -ForegroundColor Cyan
$result = Set-AuthenticodeSignature -FilePath $exePath -Certificate $cert -TimestampServer "http://timestamp.digicert.com" -HashAlgorithm SHA256

if ($result.Status -eq "Valid") {
    Write-Host "✅ EXE signed successfully!" -ForegroundColor Green
    Write-Host "   Signer : $($result.SignerCertificate.Subject)"
    Write-Host "   Status : $($result.Status)"
} else {
    Write-Warning "Signing returned status: $($result.Status)"
    Write-Warning $result.StatusMessage
}
