#!/usr/bin/env bash
set -euo pipefail

mkdir -p certs

openssl genrsa -out certs/ca.key 4096
openssl req -new -x509 -days 365 -key certs/ca.key -out certs/ca.crt -subj "/CN=ZakupAI CA"

for service in gateway risk-engine; do
  openssl genrsa -out certs/${service}.key 2048
  openssl req -new -key certs/${service}.key -out certs/${service}.csr -subj "/CN=${service}"
  openssl x509 -req -days 365 -in certs/${service}.csr -CA certs/ca.crt -CAkey certs/ca.key -CAcreateserial -out certs/${service}.crt
  rm certs/${service}.csr
done

echo "Certificates generated in ./certs"
