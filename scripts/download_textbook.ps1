# Download OpenStax Biology 2e PDF (~380 MB). Requires PowerShell 5+ or PowerShell Core.
$TargetDir = "data/docs/extracted_source_content/biology"
$TargetFile = Join-Path $TargetDir "Biology2e-WEB.pdf"
$DownloadUrl = "https://assets.openstax.org/oscms-prodcms/media/documents/Biology2e-WEB.pdf"

if (Test-Path $TargetFile) {
    $fi = Get-Item $TargetFile
    if ($fi.Length -gt 0) {
        $sizeMb = [math]::Round($fi.Length / 1MB, 1)
        Write-Host ('Textbook already exists at ' + $TargetFile + ' (' + $sizeMb + ' MB). Skipping download.')
        exit 0
    }
}

New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null
Write-Host "Downloading OpenStax Biology 2e (~380 MB)..."
Write-Host "Source: $DownloadUrl"
Write-Host "Target: $TargetFile"

try {
    $ProgressPreference = 'Continue'
    Invoke-WebRequest -Uri $DownloadUrl -OutFile $TargetFile -UseBasicParsing
} catch {
    Write-Error "Download failed: $_"
    exit 1
}

$fi = Get-Item $TargetFile
if ($fi.Length -eq 0) {
    Remove-Item $TargetFile -Force -ErrorAction SilentlyContinue
    Write-Error "Download failed; file is empty."
    exit 1
}
$sizeMb = [math]::Round($fi.Length / 1MB, 1)
$unit = ' MB'
Write-Host ('Download complete: ' + $TargetFile + ' (' + $sizeMb + $unit + ')')
