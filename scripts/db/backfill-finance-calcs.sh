#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
COMPOSE=(docker compose --profile stage6 \
  -f "$ROOT_DIR/docker-compose.yml" \
  -f "$ROOT_DIR/docker-compose.override.stage6.yml" \
  -f "$ROOT_DIR/docker-compose.override.stage6.monitoring.yml" \
  -f "$ROOT_DIR/monitoring/vault/docker-compose.override.stage6.vault.yml")

source "$ROOT_DIR/.env"
DB_USER=${POSTGRES_USER:-zakupai}
DB_NAME=${POSTGRES_DB:-zakupai}

SQL=$(cat <<'SQL'
CREATE TABLE IF NOT EXISTS finance_calcs (
  id SERIAL PRIMARY KEY,
  lot_id INTEGER,
  input JSONB NOT NULL,
  results JSONB NOT NULL,
  created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now()
);

INSERT INTO finance_calcs(lot_id, input, results)
VALUES
  (1001, '{"source":"backfill"}', '{"status":"ok"}'),
  (1002, '{"source":"backfill"}', '{"status":"ok"}'),
  (1003, '{"source":"backfill"}', '{"status":"ok"}')
ON CONFLICT DO NOTHING;
SQL
)

"${COMPOSE[@]}" exec -T db psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 -c "$SQL"

row_count() {
  "${COMPOSE[@]}" exec -T db psql -U "$DB_USER" -d "$DB_NAME" -At -c "SELECT COUNT(*) FROM finance_calcs;" \
    | tr -d '[:space:]'
}

COUNT_AFTER=$(row_count)
if [[ -z $COUNT_AFTER || $COUNT_AFTER -eq 0 ]]; then
  echo "finance_calcs backfill failed: table is empty" >&2
  exit 1
fi

printf 'finance_calcs table ready in database %s (rows=%s)\n' "$DB_NAME" "$COUNT_AFTER"
