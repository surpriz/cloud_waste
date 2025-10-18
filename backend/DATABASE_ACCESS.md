# Database Access Guide

## ⚠️ IMPORTANT: Always Use Docker PostgreSQL

CloudWaste uses a **PostgreSQL database running inside Docker**. Never use a local PostgreSQL instance.

## Quick Access

Use this alias to connect to the Docker database:

```bash
psql-cloudwaste
```

(This alias has been added to your `~/.zshrc` file)

## Manual Access

If you need to connect manually:

```bash
PGPASSWORD=cloudwaste_dev_password psql -h localhost -p 5433 -U cloudwaste -d cloudwaste
```

## Connection Details

- **Host**: `localhost` (from your Mac)
- **Port**: `5433` (forwarded to Docker container port 5432)
- **User**: `cloudwaste`
- **Password**: `cloudwaste_dev_password`
- **Database**: `cloudwaste`

## Container Access

To run queries inside the Docker container:

```bash
docker exec cloudwaste_postgres psql -U cloudwaste -d cloudwaste -c "YOUR_QUERY_HERE"
```

## Common Queries

### List all detection rules
```bash
psql-cloudwaste -c "SELECT resource_type FROM detection_rules ORDER BY created_at;"
```

### Count orphan resources
```bash
psql-cloudwaste -c "SELECT COUNT(*) FROM orphan_resources;"
```

### View recent scans
```bash
psql-cloudwaste -c "SELECT id, status, started_at, completed_at FROM scans ORDER BY started_at DESC LIMIT 5;"
```

## Troubleshooting

### "Connection refused" on port 5432
This is normal! The Docker PostgreSQL uses port **5433** (external), not 5432.

### Local PostgreSQL interfering
If you have a local PostgreSQL running, stop it:
```bash
brew services stop postgresql@15
```

### Verify Docker PostgreSQL is running
```bash
docker ps | grep postgres
```

Expected output:
```
cloudwaste_postgres   postgres:15-alpine   Up X minutes   0.0.0.0:5433->5432/tcp
```

## Architecture

```
Your Mac                          Docker Container
┌─────────────┐                   ┌──────────────────┐
│             │                   │                  │
│  localhost  │  ───5433────►     │   PostgreSQL     │
│             │                   │   (port 5432)    │
└─────────────┘                   └──────────────────┘
```

**Never connect to localhost:5432** - this will attempt to connect to a non-existent local PostgreSQL instance.

**Always use localhost:5433** - this forwards to the Docker container.
