modules:
  http_2xx:
    prober: http
    timeout: 10s
    http:
      method: GET
      valid_status_codes: []
      valid_http_versions: ["HTTP/1.0", "HTTP/1.1", "HTTP/2.0"]
      preferred_ip_protocol: "ip4"

  http_2xx_auth:
    prober: http
    timeout: 10s
    http:
      method: POST
      headers:
        Authorization: "Bearer ${GOSZAKUP_TOKEN}"
        Content-Type: "application/json"
      body: '{"query":"{ __typename }"}'
      valid_status_codes: []
      valid_http_versions: ["HTTP/1.0", "HTTP/1.1", "HTTP/2.0"]
      preferred_ip_protocol: "ip4"
