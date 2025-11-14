#!/bin/bash
# ============================================================================
# Stage 9 Secrets Test Script
# ============================================================================
# Purpose: Validate that Docker secrets are correctly mounted and readable
#          WITHOUT requiring valid B2 credentials
# ============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info() { echo -e "${BLUE}ℹ${NC} $1"; }
success() { echo -e "${GREEN}✓${NC} $1"; }
error() { echo -e "${RED}✗${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC} $1"; }

echo "============================================================================"
info "Stage 9 Docker Secrets Validation Test"
echo "============================================================================"
echo

# Test 1: Check Vault container logs for successful secret loading
info "Test 1: Checking Vault container logs for secret loading..."

# Wait for container to attempt startup
sleep 3

LOGS=$(docker logs zakupai-vault 2>&1 | tail -30)

if echo "$LOGS" | grep -q "✅ B2 credentials successfully loaded from Docker secrets"; then
  success "B2 credentials successfully loaded from Docker secrets"
else
  error "B2 credentials NOT loaded - check logs"
  exit 1
fi

if echo "$LOGS" | grep -q "✓ AWS_ACCESS_KEY_ID loaded"; then
  success "AWS_ACCESS_KEY_ID loaded successfully"
else
  error "AWS_ACCESS_KEY_ID not loaded"
  exit 1
fi

if echo "$LOGS" | grep -q "✓ AWS_SECRET_ACCESS_KEY loaded"; then
  success "AWS_SECRET_ACCESS_KEY loaded successfully"
else
  error "AWS_SECRET_ACCESS_KEY not loaded"
  exit 1
fi

# Test 2: Check if the error is about credentials (not permission denied)
info "Test 2: Verifying error type..."

if echo "$LOGS" | grep -qi "permission denied.*secrets"; then
  error "Permission denied errors found - Docker secrets mounting FAILED"
  exit 1
elif echo "$LOGS" | grep -qi "NoCredentialProviders"; then
  error "NoCredentialProviders error - credentials not being read"
  exit 1
elif echo "$LOGS" | grep -qi "InvalidAccessKeyId\|InvalidAccessKey"; then
  warn "InvalidAccessKeyId error - credentials are loaded but invalid/expired"
  info "This means Docker secrets mounting is WORKING correctly!"
  success "Docker secrets infrastructure is configured correctly"
else
  info "No specific credential errors detected"
fi

echo
echo "============================================================================"
success "Stage 9 Docker Secrets configuration is CORRECT"
echo
warn "Note: Vault requires VALID B2 credentials to start successfully."
info "If Vault is restarting, check that your B2 credentials are correct:"
echo "  1. monitoring/vault/creds/b2_access_key_id"
echo "  2. monitoring/vault/creds/b2_secret_key"
echo "============================================================================"
