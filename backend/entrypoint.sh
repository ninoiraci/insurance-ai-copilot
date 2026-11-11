#!/usr/bin/env bash
# Container entrypoint: wait for the database, migrate, seed once, then serve.
#
# Seeding is guarded by a marker table check so restarting the stack does not
# duplicate demo data. Set SKIP_BOOTSTRAP=true to serve without touching data.
set -euo pipefail

log() { printf '[entrypoint] %s\n' "$1"; }

if [ "${SKIP_BOOTSTRAP:-false}" = "true" ]; then
  log "SKIP_BOOTSTRAP=true - starting server without bootstrap"
  exec "$@"
fi

if [ -n "${DATABASE_URL:-}" ] && [[ "${DATABASE_URL}" == postgresql* ]]; then
  log "waiting for PostgreSQL…"
  for attempt in $(seq 1 40); do
    if python -c "
import os, sys
import psycopg
try:
    psycopg.connect(os.environ['DATABASE_URL'].replace('postgresql+psycopg://', 'postgresql://'), connect_timeout=2).close()
except Exception:
    sys.exit(1)
" 2>/dev/null; then
      log "PostgreSQL is ready (attempt ${attempt})"
      break
    fi
    if [ "${attempt}" -eq 40 ]; then
      log "ERROR: PostgreSQL did not become ready in time"
      exit 1
    fi
    sleep 1
  done
fi

log "applying database migrations"
flask db upgrade

# `seeded` is true when the customers table already has rows.
ALREADY_SEEDED=$(python -c "
from app import create_app
from app.extensions import db
from sqlalchemy import func, select
app = create_app()
with app.app_context():
    try:
        from app.models import Customer
        print('yes' if (db.session.scalar(select(func.count(Customer.id))) or 0) > 0 else 'no')
    except Exception:
        print('no')
" 2>/dev/null | tail -1)

if [ "${ALREADY_SEEDED}" = "yes" ]; then
  log "demo data already present - skipping seed"
else
  log "seeding synthetic demo data"
  flask seed
fi

log "ingesting knowledge base"
flask ingest-knowledge

log "starting: $*"
exec "$@"
