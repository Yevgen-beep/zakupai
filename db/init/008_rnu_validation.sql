-- RNU Validation Cache table
-- Migration 008: RNU Supplier Validation Cache

CREATE TABLE rnu_validation_cache (
    supplier_bin VARCHAR(12) PRIMARY KEY CHECK (supplier_bin ~ '^[0-9]{12}$'),
    is_blocked BOOLEAN NOT NULL,
    validated_at TIMESTAMP NOT NULL DEFAULT now(),
    expires_at TIMESTAMP NOT NULL,
    CONSTRAINT valid_bin_length CHECK (length(supplier_bin) = 12)
);

CREATE INDEX idx_rnu_validation_supplier_bin ON rnu_validation_cache (supplier_bin);
CREATE INDEX idx_rnu_validation_expires_at ON rnu_validation_cache (expires_at);

COMMENT ON TABLE rnu_validation_cache IS 'Cache for RNU supplier validation results';
COMMENT ON COLUMN rnu_validation_cache.supplier_bin IS 'Business Identification Number - exactly 12 digits';
COMMENT ON COLUMN rnu_validation_cache.is_blocked IS 'Whether the supplier is blocked in RNU registry';
COMMENT ON COLUMN rnu_validation_cache.validated_at IS 'When the validation was performed';
COMMENT ON COLUMN rnu_validation_cache.expires_at IS 'When the cache entry expires (24h TTL)';

-- Clean up expired entries periodically (can be used in cron job)
-- DELETE FROM rnu_validation_cache WHERE expires_at < now();
