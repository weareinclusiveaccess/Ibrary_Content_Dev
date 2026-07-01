# Export temporary AWS credentials for Terraform (MFA via ibrary-dev -> content-dev).
# Usage (PowerShell):
#   . .\scripts\terraform-aws-env.ps1
#   cd infra\terraform\environments\dev; terraform plan

param(
    [string]$Profile = "ibrary-dev",
    [string]$ExpectedAccount = "681986854278"
)

$ErrorActionPreference = "Stop"
$env:AWS_SDK_LOAD_CONFIG = "1"
$aws = "C:\Program Files\Amazon\AWSCLIV2\aws.exe"
if (-not (Test-Path $aws)) { $aws = "aws" }

Write-Host "Requesting credentials for profile: $Profile (MFA may prompt)..."
$lines = & $aws configure export-credentials --profile $Profile --format powershell 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error ($lines -join "`n")
}

foreach ($line in $lines) {
    if ($line -match '^\$Env:(\w+)="(.+)"\s*$') {
        Set-Item -Path "env:$($Matches[1])" -Value $Matches[2]
    }
}
Remove-Item Env:AWS_PROFILE -ErrorAction SilentlyContinue

$identity = & $aws sts get-caller-identity --output json | ConvertFrom-Json
Write-Host "OK - session credentials exported."
Write-Host "Account: $($identity.Account)"
Write-Host "Arn:     $($identity.Arn)"

if ($identity.Account -ne $ExpectedAccount) {
    Write-Error @"
Wrong AWS account. Got $($identity.Account), expected $ExpectedAccount.

Fix ~/.aws/config profile '$Profile' so it assumes:
  arn:aws:iam::681986854278:role/content-dev

Then re-run: . .\scripts\terraform-aws-env.ps1
"@
}

if ($identity.Arn -notmatch "content-dev") {
    Write-Warning "Arn does not include 'content-dev'. Terraform may still use the wrong permissions."
}
