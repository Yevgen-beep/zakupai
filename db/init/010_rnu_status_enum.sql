-- RNU Status ENUM and table updates
-- Migration 010: Extend RNU validation with status ENUM

-- Create ENUM type for RNU supplier status
CREATE TYPE rnu_supplier_status AS ENUM (
    'ACTIVE',
    'BLOCKED',
    'SUSPENDED',
    'LIQUIDATED',
    'BLACKLISTED',
    'UNKNOWN'
);

-- Add status column to rnu_validation_cache
ALTER TABLE rnu_validation_cache ADD COLUMN status rnu_supplier_status NOT NULL DEFAULT 'UNKNOWN';

-- Add index for status filtering
CREATE INDEX idx_rnu_validation_status ON rnu_validation_cache (status);

-- Update existing records to have proper status based on is_blocked
UPDATE rnu_validation_cache SET status = CASE
    WHEN is_blocked = true THEN 'BLOCKED'::rnu_supplier_status
    WHEN is_blocked = false THEN 'ACTIVE'::rnu_supplier_status
END;

-- Comments for documentation
COMMENT ON TYPE rnu_supplier_status IS 'RNU supplier validation status types';
COMMENT ON COLUMN rnu_validation_cache.status IS 'RNU supplier status: ACTIVE, BLOCKED, SUSPENDED, LIQUIDATED, BLACKLISTED, UNKNOWN';
