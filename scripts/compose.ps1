# Run Docker Compose from project root. Requires Docker Desktop (or Docker Engine) to be running.
# Usage: .\scripts\compose.ps1 up -d
$docker = "docker"
& $docker compose @args
