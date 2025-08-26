#!/usr/bin/env bash
set -euo pipefail

echo "Seeding database with test data..."
docker exec -i zakupai-db psql -U zakupai -d zakupai < scripts/seed.sql
echo "Database seeded successfully"
