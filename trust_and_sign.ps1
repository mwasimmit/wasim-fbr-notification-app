$certSubject = "CN=FBR Notification Monitor, O=Muhammad Wasim, E=mwasimmit@gmail.com"
$cert = Get-ChildItem "Cert:\CurrentUser\My" -CodeSigningCert | Where-Object { $_.Subject -eq $certSubject } | Select-Object -First 1
if (-not $cert) {
    $cert = New-SelfSignedCertificate -Subject $certSubject -CertStoreLocation "Cert:\CurrentUser\My" -KeyUsage DigitalSignature -Type CodeSigningCert -NotAfter (Get-Date).AddYears(5) -HashAlgorithm SHA256
}
Write-Host "Using cert: $($cert.Thumbprint)"

# Trust in CurrentUser Root store
$store = New-Object System.Security.Cryptography.X509Certificates.X509Store("Root","CurrentUser")
$store.Open("ReadWrite")
$store.Add($cert)
$store.Close()
Write-Host "Trusted in CurrentUser Root."

# Sign WITHOUT timestamp server (avoids network hang)
$exePath = "D:\gen_Learning\Anti_Gravity\agy-cli-projects\bq-releases-notes\dist\FBRNotificationMonitor.exe"
$result = Set-AuthenticodeSignature -FilePath $exePath -Certificate $cert -HashAlgorithm SHA256
Write-Host "Signing status: $($result.Status)"
if ($result.SignerCertificate) {
    Write-Host "Signer: $($result.SignerCertificate.Subject)"
} else {
    Write-Host "StatusMessage: $($result.StatusMessage)"
}
