#!/bin/bash
# ===========================================
# Generate Self-Signed TLS Certificates for Vault
# ===========================================
# Usage: ./monitoring/vault/tls/generate-certs.sh
#
# This script generates:
# - CA certificate (ca.crt, ca.key)
# - Vault server certificate (server.crt, server.key)
#
# ⚠️ For development only! Use proper PKI in production.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

DAYS=3650  # 10 years (dev only)
COUNTRY="KZ"
STATE="Almaty"
CITY="Almaty"
ORG="ZakupAI"
OU="DevOps"
CN_CA="ZakupAI Root CA"
CN_SERVER="vault"

echo "🔐 Generating TLS certificates for Vault..."

# ===========================================
# 1. Generate CA (Certificate Authority)
# ===========================================

if [ -f "ca.key" ]; then
  echo "⚠️  CA key already exists, skipping CA generation"
else
  echo "📝 Creating CA private key..."
  openssl genrsa -out ca.key 4096

  echo "📝 Creating CA certificate..."
  openssl req -x509 -new -nodes -key ca.key -sha256 -days ${DAYS} -out ca.crt \
    -subj "/C=${COUNTRY}/ST=${STATE}/L=${CITY}/O=${ORG}/OU=${OU}/CN=${CN_CA}"

  echo "✅ CA certificate created: ca.crt"
fi

# ===========================================
# 2. Generate Vault Server Certificate
# ===========================================

echo "📝 Creating Vault server private key..."
openssl genrsa -out server.key 2048

echo "📝 Creating certificate signing request (CSR)..."
openssl req -new -key server.key -out server.csr \
  -subj "/C=${COUNTRY}/ST=${STATE}/L=${CITY}/O=${ORG}/OU=${OU}/CN=${CN_SERVER}"

# Create openssl config for SAN (Subject Alternative Names)
cat > server.ext <<EOF
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature, nonRepudiation, keyEncipherment, dataEncipherment
subjectAltName = @alt_names

[alt_names]
DNS.1 = vault
DNS.2 = localhost
DNS.3 = zakupai-vault
DNS.4 = vault.zakupai.local
IP.1 = 127.0.0.1
IP.2 = 0.0.0.0
EOF

echo "📝 Signing server certificate with CA..."
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key \
  -CAcreateserial -out server.crt -days ${DAYS} -sha256 \
  -extfile server.ext

# Clean up temporary files
rm -f server.csr server.ext

echo "✅ Vault server certificate created: server.crt, server.key"

# ===========================================
# 3. Verify certificates
# ===========================================

echo ""
echo "🔍 Verifying certificates..."
openssl x509 -in ca.crt -noout -subject -dates
openssl x509 -in server.crt -noout -subject -dates -ext subjectAltName

echo ""
echo "✅ TLS certificates generated successfully!"
echo ""
echo "📁 Files created:"
echo "   - ca.crt       (CA certificate)"
echo "   - ca.key       (CA private key)"
echo "   - server.crt   (Vault server certificate)"
echo "   - server.key   (Vault server private key)"
echo ""
echo "⚠️  Next steps:"
echo "   1. Set proper permissions (DO NOT RUN - documentation only):"
echo "      chmod 600 server.key ca.key"
echo "      chmod 644 server.crt ca.crt"
echo "      chown 100:1000 server.* ca.*  # vault user in container"
echo ""
echo "   2. Verify Vault can read certificates:"
echo "      docker exec zakupai-vault ls -la /vault/tls/"
echo ""
echo "   3. Test TLS connection:"
echo "      curl --cacert ca.crt https://localhost:8200/v1/sys/health"
