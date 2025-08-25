#!/usr/bin/env bash
set -euo pipefail

if [ ! -f ".env" ]; then
  echo "Создаю .env из .env.example"
  cp .env.example .env
fi

echo "Старт docker compose..."
docker compose up -d --build

echo "Готово. Проверка:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
