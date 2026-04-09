# TARA

## Docker Compose

This repo includes a `docker-compose.yml` with these services:

- Redis (`localhost:6379`)
- PostgreSQL (`localhost:5432`)
- GitLab CE (`http://localhost:8080`, SSH on `localhost:2222`)
- TARA (Python dev container; mounts the current directory into `/app`)

## Database scripts

Database utilities live in `scripts/db.py` and use `DATABASE_URL`.

### Examples

```bash
# Start services
docker compose up -d

# Show connection info (reads DATABASE_URL)
python scripts/db.py info

# Wait for Postgres to be reachable
python scripts/db.py wait

# Create tables (idempotent)
python scripts/db.py schema

# Insert seed data (safe to re-run)
python scripts/db.py seed

# Reset public schema (DESTRUCTIVE) then re-apply schema+seed
python scripts/db.py reset --with-schema --with-seed

# Dump/restore
python scripts/db.py dump --out backups/tara.sql
python scripts/db.py restore backups/tara.sql
```

### Start

```bash
docker compose up -d
```

### Stop

```bash
docker compose down
```

### Notes

- GitLab initial startup can take a while (first boot provisions data).
- If you want GitLab reachable by hostname (instead of `localhost`), update `external_url` in `docker-compose.yml`.