#!/bin/sh
set -eu

# Wrapper entrypoint to hydrate AWS credentials from docker secrets files
# before invoking the official Vault entrypoint.
#
# CRITICAL: AWS SDK does NOT support *_FILE variables natively.
# We must read the secrets and export them as AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY.

echo "🔧 Stage 9 Vault B2 Entrypoint - Starting..."

# Check if secrets directory exists
if [ -d "/run/secrets" ]; then
  echo "✓ /run/secrets directory exists"
  ls -la /run/secrets/ 2>/dev/null || echo "⚠️  Cannot list /run/secrets (permission denied - this is normal)"
else
  echo "✗ /run/secrets directory does NOT exist - Docker secrets not mounted!"
  exit 1
fi

# Read B2 access key from Docker secret
if [ -n "${AWS_ACCESS_KEY_ID_FILE:-}" ] && [ -f "$AWS_ACCESS_KEY_ID_FILE" ]; then
  echo "✓ Reading AWS_ACCESS_KEY_ID from: $AWS_ACCESS_KEY_ID_FILE"
  # Read the file and export as environment variable
  AWS_ACCESS_KEY_ID=$(cat "$AWS_ACCESS_KEY_ID_FILE")
  export AWS_ACCESS_KEY_ID
  echo "✓ AWS_ACCESS_KEY_ID loaded (length: ${#AWS_ACCESS_KEY_ID} chars)"
else
  echo "✗ AWS_ACCESS_KEY_ID_FILE not set or file not found: ${AWS_ACCESS_KEY_ID_FILE:-<not set>}"
  exit 1
fi

# Read B2 secret key from Docker secret
if [ -n "${AWS_SECRET_ACCESS_KEY_FILE:-}" ] && [ -f "$AWS_SECRET_ACCESS_KEY_FILE" ]; then
  echo "✓ Reading AWS_SECRET_ACCESS_KEY from: $AWS_SECRET_ACCESS_KEY_FILE"
  # Read the file and export as environment variable
  AWS_SECRET_ACCESS_KEY=$(cat "$AWS_SECRET_ACCESS_KEY_FILE")
  export AWS_SECRET_ACCESS_KEY
  echo "✓ AWS_SECRET_ACCESS_KEY loaded (length: ${#AWS_SECRET_ACCESS_KEY} chars)"
else
  echo "✗ AWS_SECRET_ACCESS_KEY_FILE not set or file not found: ${AWS_SECRET_ACCESS_KEY_FILE:-<not set>}"
  exit 1
fi

echo "✅ B2 credentials successfully loaded from Docker secrets"
echo "🚀 Launching Vault server..."
echo ""

# Execute the official Vault entrypoint
# Vault will now see AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in environment
exec /usr/local/bin/docker-entrypoint.sh server
