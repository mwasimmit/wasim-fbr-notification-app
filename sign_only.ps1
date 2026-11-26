$certSubject = 'CN=FBR Notification Monitor, O=Muhammad Wasim, E=mwasimmit@gmail.com'
$cert = Get-ChildItem 'Cert:\CurrentUser\My' -CodeSigningCert |
        Where-Object { $_.Subject -eq $certSubject } |
        Select-Object -First 1

if (-not $cert) {
    $cert = New-SelfSignedCertificate -Subject $certSubject `
        -CertStoreLocation 'Cert:\CurrentUser\My' `
        -KeyUsage DigitalSignature `
        -Type CodeSigningCert `
        -NotAfter (Get-Date).AddYears(5) `
        -HashAlgorithm SHA256
    Write-Host 'Certificate created.'
} else {
    Write-Host 'Using existing certificate.'
}

$thumb = $cert.Thumbprint
Write-Host "Thumbprint: $thumb"

$exePath = 'D:\gen_Learning\Anti_Gravity\agy-cli-projects\bq-releases-notes\dist\FBRNotificationMonitor.exe'
$result = Set-AuthenticodeSignature -FilePath $exePath -Certificate $cert -HashAlgorithm SHA256

$status = $result.Status
Write-Host "Signing status: $status"
if ($result.SignerCertificate) {
    $signer = $result.SignerCertificate.Subject
    Write-Host "Signer: $signer"
}
