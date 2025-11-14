#!/bin/bash
# ============================================================================
# TLS Certificates Generator for Vault Stage 9
# ============================================================================
# Purpose: Generate self-signed certificates with correct permissions
# Usage: ./generate-certs.sh [--docker-volume]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VOLUME_NAME="zakupai_vault_tls"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== Vault TLS Certificate Generator ===${NC}\n"

if [[ "${1:-}" == "--docker-volume" ]]; then
    echo -e "${YELLOW}📦 Generating certificates directly in Docker volume${NC}"
    docker run --rm -v ${VOLUME_NAME}:/vault/tls alpine sh -c "
        apk add --no-cache openssl > /dev/null 2>&1;
        cd /vault/tls;
        echo '🔐 Generating private key...';
        openssl genrsa -out vault.key 2048 2>/dev/null;
        echo '📜 Generating certificate...';
        openssl req -new -x509 -key vault.key -out vault.crt \
            -days 365 \
            -subj '/C=KZ/ST=Karaganda/L=Karagandy/O=ZakupAI/CN=vault' 2>/dev/null;
        echo '🔒 Setting permissions (UID 100:100)...';
        chown 100:100 vault.key vault.crt;
        chmod 640 vault.key;
        chmod 644 vault.crt;
        echo '✅ Certificates generated:';
        ls -la /vault/tls;"
    echo -e "\n${GREEN}✅ Certificates created in Docker volume: ${VOLUME_NAME}${NC}"
else
    echo -e "${YELLOW}📁 Generating certificates in local directory${NC}"
    openssl genrsa -out "${SCRIPT_DIR}/vault.key" 2048 2>/dev/null
    openssl req -new -x509 -key "${SCRIPT_DIR}/vault.key" -out "${SCRIPT_DIR}/vault.crt" \
        -days 365 -subj "/C=KZ/ST=Karaganda/L=Karagandy/O=ZakupAI/CN=vault" 2>/dev/null
    chmod 640 "${SCRIPT_DIR}/vault.key"
    chmod 644 "${SCRIPT_DIR}/vault.crt"
    echo -e "\n${GREEN}✅ Certificates created in: ${SCRIPT_DIR}${NC}"
    ls -la "${SCRIPT_DIR}"/vault.{key,crt}
    echo -e "\n${YELLOW}⚠️  Note: Permissions will be fixed by init-container${NC}"
fi
echo -e "\n${GREEN}🎉 Certificate generation complete!${NC}"
