# Open a psql shell inside the Postgres container. Run from project root.
# Usage: .\scripts\postgres-shell.ps1
# Connects as ibrary (the user created from .env POSTGRES_USER).
docker exec -it ibrary-postgres psql -U ibrary -d ibrary
