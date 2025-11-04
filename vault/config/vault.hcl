storage "file" {
  path = "/vault/data"
}

listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = true
}

disable_mlock = true
ui            = true
disable_cache = true
api_addr      = "http://vault:8200"
