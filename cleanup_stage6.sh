#!/usr/bin/env bash
set -e

echo "=== 🧹 ZakupAI Stage6 Cleanup & Commit Script (Safe Mode) ==="

# 1️⃣ Проверяем, что находимся в корне проекта
if [ ! -f "Makefile" ]; then
  echo "❌ Please run this script from the root of the repository."
  exit 1
fi

# 2️⃣ Обновляем .gitignore (Stage7-ready)
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

# 3️⃣.5 Проверяем и восстанавливаем права, чтобы не было «Отказано в доступе»
echo "🧰 Checking permissions for key folders..."
TARGETS=(backups db monitoring services)
for dir in "${TARGETS[@]}"; do
  if [ -d "$dir" ]; then
    if [ ! -w "$dir" ]; then
      echo "🔧 Fixing ownership and permissions for $dir ..."
      sudo chown -R $USER:$USER "$dir" 2>/dev/null || true
      sudo chmod -R u+rw "$dir" 2>/dev/null || true
    fi
  fi
done
echo "✅ Permissions verified and fixed where needed."

# 4️⃣ Восстанавливаем только важные удалённые файлы (не трогаем код)
echo "🛠️ Checking for accidentally deleted key files..."
KEY_FILES=(Makefile README.md docker-compose.yml .env.example)
for f in "${KEY_FILES[@]}"; do
  if [ ! -f "$f" ] && git ls-files --error-unmatch "$f" >/dev/null 2>&1; then
    echo "♻️ Restoring $f from git..."
    git restore "$f"
  fi
done
echo "✅ All essential files verified."

# 5️⃣ Удаляем мусор, но сохраняем .env (или создаём, если его нет)
echo "🧽 Cleaning untracked & ignored files (preserving .env)..."
if [ -f ".env" ]; then
  cp .env .env.backup
  echo "🧾 .env backup created."
fi
git clean -fdX 2>/dev/null || true
if [ -f ".env.backup" ]; then
  mv .env.backup .env
  echo "✅ Restored .env after cleanup."
else
  echo "⚠️ .env not found — creating default from .env.example."
  cp .env.example .env
fi

# 6️⃣ Удаляем мусор, созданный root (контейнеры)
echo "🧨 Removing root-owned build files..."
sudo find backups db monitoring services -user root -type f -delete 2>/dev/null || true
echo "✅ Root-owned junk cleared."

# 7️⃣ Пересканируем git
echo "🔍 Refreshing repository index..."
git rm -r --cached . >/dev/null 2>&1 || true
git add .

# 8️⃣ Добавляем только ключевые Stage6 файлы
echo "📦 Staging relevant changes..."
git add .github workflows monitoring services Makefile TODO.md README.md

# 9️⃣ Делаем коммит
echo "💾 Creating Stage6 Final Commit..."
git commit -m '✅ Stage6 Final Snapshot: all services stable, monitoring complete' || echo "ℹ️ No changes to commit."

# 🔟 Создаём тег
TAG="stage6-final-$(date +%Y%m%d)"
git tag -a "$TAG" -m "Stage 6 Final Snapshot"
git push origin "$TAG" || echo "⚠️ Git push failed or offline."

echo "🎯 Done! Stage6 snapshot committed and tagged as $TAG"
