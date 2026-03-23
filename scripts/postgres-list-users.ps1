# List all PostgreSQL users/roles. Run from project root.
docker exec ibrary-postgres psql -U ibrary -d ibrary -c "SELECT rolname AS username, rolsuper AS superuser, rolcreatedb AS create_db, rolcanlogin AS can_login FROM pg_roles WHERE rolcanlogin ORDER BY rolname;"
