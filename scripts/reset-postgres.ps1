# Reset PostgreSQL container and volume so it is created with credentials from .env,
# then run migrations. Use this if you see "password authentication failed for user ibrary".
# Run from project root: .\scripts\reset-postgres.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
if (-not (Test-Path (Join-Path $root "docker-compose.yml"))) {
    $root = Get-Location
}
Set-Location $root
Write-Host "Stopping containers and removing Postgres volume..."
docker compose down -v
Write-Host "Starting fresh Postgres and DynamoDB..."
docker compose up -d
Write-Host "Waiting 10s for Postgres to initialize..."
Start-Sleep -Seconds 10
Write-Host "Running migrations..."
uv run alembic upgrade head
Write-Host "Done. You can run: uv run python scripts/create_dynamodb_tables.py"
Set-Location $root
