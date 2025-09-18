-- ETL Batch Uploads table for mass data loading
-- Migration 007: ETL Batch Uploads

CREATE TABLE etl_batch_uploads (
    id SERIAL PRIMARY KEY,
    bin VARCHAR(12) NOT NULL CHECK (bin ~ '^[0-9]{12}$'),
    amount NUMERIC(18,2) NOT NULL CHECK (amount >= 0),
    status VARCHAR(50) NOT NULL CHECK (status IN ('NEW','APPROVED','REJECTED')),
    created_at TIMESTAMP DEFAULT now(),
    batch_id UUID NOT NULL
);

CREATE INDEX idx_etl_batch_uploads_batch_id ON etl_batch_uploads (batch_id);
CREATE INDEX idx_etl_batch_uploads_bin ON etl_batch_uploads (bin);
CREATE INDEX idx_etl_batch_uploads_created_at ON etl_batch_uploads (created_at);

COMMENT ON TABLE etl_batch_uploads IS 'Stores batch-uploaded transaction data';
COMMENT ON COLUMN etl_batch_uploads.bin IS 'Business Identification Number - exactly 12 digits';
COMMENT ON COLUMN etl_batch_uploads.amount IS 'Transaction amount with 2 decimal precision';
COMMENT ON COLUMN etl_batch_uploads.status IS 'Transaction status: NEW, APPROVED, or REJECTED';
COMMENT ON COLUMN etl_batch_uploads.batch_id IS 'UUID identifying the batch upload session';
