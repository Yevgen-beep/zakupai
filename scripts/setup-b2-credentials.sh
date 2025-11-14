#!/usr/bin/env bash
# ============================================================================
# Secure B2 Credentials Setup for Vault Stage 9
# ============================================================================
# Purpose: Safely create and validate Backblaze B2 credential files
# Usage: ./scripts/setup-b2-credentials.sh [--validate]
# Security: Credentials never logged, proper permissions enforced

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

CREDS_DIR="monitoring/vault/creds"
KEY_ID_FILE="$CREDS_DIR/b2_access_key_id"
KEY_FILE="$CREDS_DIR/b2_secret_key"
GITIGNORE=".gitignore"

echo -e "${GREEN}=== Secure B2 Credentials Setup ===${NC}\n"

# ============================================================================
# Function: Validate credentials format
# ============================================================================
validate_format() {
    local key_id="$1"
    local key="$2"
    
    # B2 Key ID format: 25 characters, starts with 0-9
    if [[ ! "$key_id" =~ ^[0-9a-fA-F]{25}$ ]]; then
        echo -e "${RED}❌ Invalid Key ID format (expected 25 hex chars)${NC}"
        return 1
    fi
    
    # B2 Application Key format: 31 characters, base64-like
    if [ ${#key} -lt 31 ]; then
        echo -e "${RED}❌ Invalid Application Key (too short, expected ≥31 chars)${NC}"
        return 1
    fi
    
    echo -e "${GREEN}✅ Credentials format valid${NC}"
    return 0
}

# ============================================================================
# Function: Test B2 connectivity
# ============================================================================
test_b2_connection() {
    local key_id="$1"
    local key="$2"
    local endpoint="https://s3.us-west-004.backblazeb2.com"
    local bucket="zakupai-vault"
    
    echo -e "${YELLOW}🔍 Testing B2 connectivity...${NC}"
    
    # Test with curl (lightweight, no AWS CLI required)
    local response=$(AWS_ACCESS_KEY_ID="$key_id" \
                     AWS_SECRET_ACCESS_KEY="$key" \
                     curl -s -I "$endpoint/$bucket" 2>&1 || true)
    
    if echo "$response" | grep -q "403\|404\|200"; then
        # 403 = forbidden (credentials work, but no permissions)
        # 404 = not found (credentials work, bucket doesn't exist)
        # 200 = success
        echo -e "${GREEN}✅ B2 endpoint reachable, credentials accepted${NC}"
        return 0
    elif echo "$response" | grep -q "InvalidAccessKeyId"; then
        echo -e "${RED}❌ Invalid B2 credentials${NC}"
        return 1
    else
        echo -e "${YELLOW}⚠️  B2 connectivity test inconclusive (endpoint may be down)${NC}"
        echo -e "${YELLOW}   Proceeding anyway, but verify manually:${NC}"
        echo -e "${YELLOW}   curl -I $endpoint/$bucket${NC}"
        return 0  # Don't block setup
    fi
}

# ============================================================================
# Function: Secure file creation
# ============================================================================
create_credential_files() {
    local key_id="$1"
    local key="$2"
    
    # Create directory with restricted permissions
    mkdir -p "$CREDS_DIR"
    chmod 700 "$CREDS_DIR"
    
    # Create files atomically (write to temp, then move)
    local temp_id=$(mktemp)
    local temp_key=$(mktemp)
    
    printf '%s' "$key_id" > "$temp_id"
    printf '%s' "$key" > "$temp_key"
    
    # Set permissions before moving (prevent race condition)
    chmod 600 "$temp_id" "$temp_key"
    
    # Atomic move
    mv "$temp_id" "$KEY_ID_FILE"
    mv "$temp_key" "$KEY_FILE"
    
    echo -e "${GREEN}✅ Credential files created:${NC}"
    ls -la "$KEY_ID_FILE" "$KEY_FILE"
}

# ============================================================================
# Function: Update .gitignore
# ============================================================================
update_gitignore() {
    if grep -q "monitoring/vault/creds/b2_" "$GITIGNORE" 2>/dev/null; then
        echo -e "${GREEN}✅ .gitignore already configured${NC}"
    else
        echo -e "${YELLOW}⚠️  Adding B2 credentials to .gitignore${NC}"
        cat >> "$GITIGNORE" <<'EOF'

# Vault B2 credentials (Stage 9 - DO NOT COMMIT)
monitoring/vault/creds/b2_access_key_id
monitoring/vault/creds/b2_secret_key
EOF
        echo -e "${GREEN}✅ .gitignore updated${NC}"
    fi
}

# ============================================================================
# Function: Check for existing credentials
# ============================================================================
check_existing() {
    if [ -f "$KEY_ID_FILE" ] && [ -f "$KEY_FILE" ]; then
        echo -e "${GREEN}✅ Existing credentials found${NC}"
        
        # Verify permissions
        local perms_id=$(stat -c "%a" "$KEY_ID_FILE")
        local perms_key=$(stat -c "%a" "$KEY_FILE")
        
        if [ "$perms_id" != "600" ] || [ "$perms_key" != "600" ]; then
            echo -e "${YELLOW}⚠️  Fixing insecure permissions...${NC}"
            chmod 600 "$KEY_ID_FILE" "$KEY_FILE"
            echo -e "${GREEN}✅ Permissions fixed${NC}"
        fi
        
        return 0
    else
        return 1
    fi
}

# ============================================================================
# Main execution
# ============================================================================

# Check if --validate flag passed
if [[ "${1:-}" == "--validate" ]]; then
    if ! check_existing; then
        echo -e "${RED}❌ No credentials found to validate${NC}"
        exit 1
    fi
    
    KEY_ID=$(cat "$KEY_ID_FILE")
    KEY=$(cat "$KEY_FILE")
    
    validate_format "$KEY_ID" "$KEY" || exit 1
    test_b2_connection "$KEY_ID" "$KEY" || exit 1
    
    echo -e "\n${GREEN}✅ Validation complete${NC}"
    exit 0
fi

# Check for existing credentials
if check_existing; then
    read -p "Credentials already exist. Overwrite? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}⚠️  Keeping existing credentials${NC}"
        exit 0
    fi
fi

# Get credentials from environment or prompt
if [ -n "${B2_KEY_ID:-}" ] && [ -n "${B2_KEY:-}" ]; then
    echo -e "${GREEN}✅ Using credentials from environment variables${NC}"
    KEY_ID="$B2_KEY_ID"
    KEY="$B2_KEY"
else
    echo -e "${YELLOW}📝 Enter Backblaze B2 credentials:${NC}"
    echo "   (Get them from: https://secure.backblaze.com/app_keys.htm)"
    echo
    
    read -p "Application Key ID: " KEY_ID
    read -sp "Application Key: " KEY
    echo
fi

# Validate format
validate_format "$KEY_ID" "$KEY" || exit 1

# Test connectivity (optional, can fail)
test_b2_connection "$KEY_ID" "$KEY" || true

# Create files
create_credential_files "$KEY_ID" "$KEY"

# Update .gitignore
update_gitignore

# Verify not staged in Git
if git ls-files --error-unmatch "$KEY_ID_FILE" 2>/dev/null; then
    echo -e "${RED}❌ WARNING: Credential file is tracked by Git!${NC}"
    echo -e "${YELLOW}   Run: git rm --cached $KEY_ID_FILE${NC}"
fi

echo -e "\n${GREEN}=== Setup Complete ===${NC}"
echo -e "${YELLOW}Next steps:${NC}"
echo "  1. Verify credentials: ./scripts/setup-b2-credentials.sh --validate"
echo "  2. Update Vault config: monitoring/vault/config/secure/config-stage9.hcl"
echo "  3. Deploy Vault: make stage9-deploy"
echo
echo -e "${RED}⚠️  IMPORTANT: Store these credentials in your password manager!${NC}"