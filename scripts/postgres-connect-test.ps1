# Test TCP connection to Postgres using the same host/port/user/password as pgAdmin.
# Run from project root. Uses a temporary postgres client container.
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

# Read password from .env
$envLine = Get-Content .env -ErrorAction SilentlyContinue | Where-Object { $_ -match '^POSTGRES_PASSWORD=' }
if (-not $envLine) {
    Write-Host "Could not find POSTGRES_PASSWORD in .env"
    exit 1
}
$password = ($envLine -split '=', 2)[1].Trim()

$port = 5433
$portLine = Get-Content .env -ErrorAction SilentlyContinue | Where-Object { $_ -match '^POSTGRES_PORT=' }
if ($portLine) { $port = ($portLine -split '=', 2)[1].Trim() }
Write-Host "Testing TCP connection to 127.0.0.1:${port} as user ibrary (password from .env)..."
docker run --rm -e "PGPASSWORD=$password" postgres:16 psql -h host.docker.internal -p $port -U ibrary -d ibrary -c "SELECT current_user AS connected_as;"
if ($LASTEXITCODE -eq 0) {
    Write-Host "Connection OK. Use in pgAdmin: Host 127.0.0.1, Port $port, User ibrary, Password (from .env)."
} else {
    Write-Host "Connection failed. Ensure containers are up (.\scripts\compose.ps1 up -d) and password in .env matches Postgres."
}
