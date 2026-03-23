# Makefile parity for Windows when GNU make is not installed.
# Run from repo root:
#   pwsh -File scripts/make.ps1 pipeline
#   .\scripts\make.ps1 help
# Resume examples:
#   $env:STEP = "align"; .\scripts\make.ps1 pipeline-resume
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

function Show-Help {
    @"
Available targets (same names as Makefile):
  help                 Show this list
  up                   docker compose up -d
  down                 docker compose down
  ps                   docker compose ps
  db-migrate           uv run alembic upgrade head
  dynamodb-setup       uv run python scripts/create_dynamodb_tables.py
  download-textbook    Download OpenStax Biology 2e PDF (PowerShell)
  pipeline             uv run python scripts/run_pipeline.py
  pipeline-full        uv run python scripts/run_pipeline.py --full
  pipeline-resume      Requires `$env:STEP (extract|validate|align|...)
  pipeline-full-resume Requires `$env:STEP for curate+ resume

Examples:
  .\scripts\make.ps1 pipeline
  `$env:STEP = 'curate'; .\scripts\make.ps1 pipeline-full-resume
"@
}

$Target = if ($args.Count -ge 1) { $args[0] } else { "help" }

switch ($Target) {
    "help" {
        Show-Help
    }
    "up" {
        docker compose up -d
    }
    "down" {
        docker compose down
    }
    "ps" {
        docker compose ps
    }
    "db-migrate" {
        uv run alembic upgrade head
    }
    "dynamodb-setup" {
        uv run python scripts/create_dynamodb_tables.py
    }
    "download-textbook" {
        & (Join-Path $PSScriptRoot "download_textbook.ps1")
    }
    "pipeline" {
        uv run python scripts/run_pipeline.py
    }
    "pipeline-full" {
        uv run python scripts/run_pipeline.py --full
    }
    "pipeline-resume" {
        if (-not $env:STEP) {
            throw "pipeline-resume requires environment variable STEP (e.g. extract, validate, align)."
        }
        uv run python scripts/run_pipeline.py --resume-from $env:STEP
    }
    "pipeline-full-resume" {
        if (-not $env:STEP) {
            throw "pipeline-full-resume requires environment variable STEP (e.g. curate)."
        }
        uv run python scripts/run_pipeline.py --full --resume-from $env:STEP
    }
    default {
        Write-Error "Unknown target '$Target'. Run .\scripts\make.ps1 help"
        exit 1
    }
}
