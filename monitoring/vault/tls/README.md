# Vault TLS Certificates

This directory contains TLS certificates for Vault HTTPS connections (Stage 9).

## Files

### `vault-cert.pem` (gitignored)
Public certificate for Vault HTTPS listener.

**Valid for**:
- CN: vault.zakupai.local
- SAN: vault.zakupai.local, localhost, 127.0.0.1
- Key length: RSA 4096-bit
- Validity: 365 days

### `vault-key.pem` (gitignored)
Private key for TLS certificate.

**⚠️ CRITICAL**: This file must be kept secure with `600` permissions.

## Certificate Generation

### Self-Signed Certificate (Development/Staging)
```bash
make vault-tls-renew
```

This generates a self-signed certificate valid for 1 year.

### Let's Encrypt Certificate (Production)

For production with a public domain, use Let's Encrypt:

```bash
# Install certbot
sudo apt-get install certbot

# Generate certificate
sudo certbot certonly --standalone \
    -d vault.zakupai.com \
    --non-interactive \
    --agree-tos \
    --email admin@zakupai.com

# Copy certificates
sudo cp /etc/letsencrypt/live/vault.zakupai.com/fullchain.pem \
    monitoring/vault/tls/vault-cert.pem
sudo cp /etc/letsencrypt/live/vault.zakupai.com/privkey.pem \
    monitoring/vault/tls/vault-key.pem

# Set permissions
chmod 644 monitoring/vault/tls/vault-cert.pem
chmod 600 monitoring/vault/tls/vault-key.pem
```

### Certificate Auto-Renewal

Add to crontab for Let's Encrypt auto-renewal:
```bash
0 3 * * * certbot renew --quiet --post-hook "make vault-tls-renew && docker restart vault"
```

## Certificate Verification

### Check certificate expiry
```bash
openssl x509 -in vault-cert.pem -noout -enddate
```

### Check certificate details
```bash
openssl x509 -in vault-cert.pem -text -noout
```

### Check if certificate expires in <30 days
```bash
openssl x509 -in vault-cert.pem -noout -checkend 2592000 && \
    echo "Certificate is valid" || \
    echo "Certificate expires soon - renew now!"
```

### Test TLS connection
```bash
openssl s_client -connect 127.0.0.1:8200 -servername vault.zakupai.local
```

## Prometheus Monitoring

Prometheus alerts are configured to warn when:
- Certificate expires in <30 days (`VaultTLSCertExpiringSoon`)
- Certificate has expired (`VaultTLSCertExpired`)

Check: `monitoring/prometheus/alerts/vault.yml`

## Troubleshooting

### "SSL certificate problem: self signed certificate"

For development with self-signed certificates:
```bash
export VAULT_SKIP_VERIFY=true
```

**⚠️ WARNING**: Never use `VAULT_SKIP_VERIFY=true` in production!

### Certificate not trusted by services

Add certificate to system trust store:
```bash
sudo cp monitoring/vault/tls/vault-cert.pem /usr/local/share/ca-certificates/vault.crt
sudo update-ca-certificates
```

### Restart required after renewal

Always restart Vault after certificate renewal:
```bash
docker restart vault
```

## Security Best Practices

1. **Private key permissions**: Always `600` (owner read/write only)
2. **Certificate rotation**: Rotate every 90 days (Let's Encrypt default)
3. **Key length**: Minimum 2048-bit RSA, recommended 4096-bit
4. **TLS version**: Minimum TLS 1.2 (configured in `config-stage9.hcl`)
5. **Cipher suites**: Only strong ciphers (ECDHE + AES-GCM)
