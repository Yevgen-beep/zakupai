#!/usr/bin/env bash
set -e

echo "=== 🧹 ZakupAI Stage6 Cleanup & Commit Script ==="

# 1️⃣ Проверяем, что находимся в корне проекта
if [ ! -f "Makefile" ]; then
  echo "❌ Please run this script from the root of the repository."
  exit 1
fi

# 2️⃣ Обновляем .gitignore до Stage7-ready версии
cat > .gitignore <<'EOF'
# ============================================
# 🔒 ZakupAI .gitignore (Stage6/Stage7 Ready)
# ============================================

# --- Environment variables and secrets ---
.env
.env.*
*.env
!.env.example

# --- Virtual environments ---
.venv/
venv/

# --- API keys and secrets ---
*.key
*.pem
*.p12
*.pfx
secrets/
credentials/
vault-secrets/
vault-backups/

# --- Database dumps and backups ---
*.sql
*.sql.gz
*.dump
*.bak*
*.backup
backups/

# --- Logs ---
*.log
logs/
nohup.out

# --- Temporary / cache files ---
*.tmp
*.temp
.DS_Store
Thumbs.db
*.swp
*.swo
.cache/
pytestdebug.log

# --- IDE / Editor ---
.vscode/
.idea/
*.code-workspace

# --- Python build / cache ---
__pycache__/
*.pyc
*.pyo
*.pyd
.pytest_cache/
.coverage
htmlcov/
*.egg-info/
*.egg/
.eggs/

# --- Docker volumes / data ---
data/
volumes/
n8n-nodes/*/node_modules/
n8n_data/
flowise_data/

# --- Monitoring and Vault secrets ---
monitoring/vault/tls/*
monitoring/prometheus/vault-metrics.token
monitoring/**/*.bak*
monitoring/**/*.diff

# --- Stage / backup / diff files ---
*.diff
*.orig
stage*_fix_*.py
stage*_report*.md
*_backup.sh
*_snapshot.sh
*_debug.sh
*_test.sh
stage*-*.sh

# --- Test and mock data ---
test_files/
tests_output/
services/etl-service/test_files/
services/*/tests/__pycache__/
services/*/tests/test_validation*.pyc

# --- Generated init and metadata ---
services/__init__.py
services/*/__init__.py
libs/**/*.egg-info/
libs/**/*.dist-info/

# --- Local deployment artifacts ---
docker-compose.override.*.bak
docker-compose.yml.bak
Makefile.bak
README*.bak
*.bak_*
*.bak-*

# --- Misc ---
web/main_fixed.py
stage6_*.diff
stage7_*.diff
EOF

echo "✅ .gitignore updated."

# 3️⃣ Восстанавливаем случайно удалённые файлы
git restore .

# 4️⃣ Удаляем весь мусор (кэш, __pycache__, .bak и т.п.)
echo "🧽 Cleaning untracked & ignored files..."
git clean -fdX

# 5️⃣ Пересканируем git
echo "🔍 Refreshing repository index..."
git rm -r --cached .
git add .

# 6️⃣ Добавляем только ключевые Stage6 файлы
echo "📦 Staging relevant changes..."
git add .github workflows monitoring services Makefile TODO.md README.md

# 7️⃣ Делаем коммит
echo "💾 Creating Stage6 Final Commit..."
git commit -m '✅ Stage6 Final Snapshot: all services stable, monitoring complete'

# 8️⃣ Создаём тег
TAG="stage6-final-$(date +%Y%m%d)"
git tag -a "$TAG" -m "Stage 6 Final Snapshot"
git push origin "$TAG"

echo "🎯 Done! Stage6 snapshot committed and tagged as $TAG"
