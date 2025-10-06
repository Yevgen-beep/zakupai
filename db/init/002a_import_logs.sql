-- Migration 012: CSV Import Logs
-- Week 4.1: Web UI CSV import functionality
-- Note: prices table already exists in 002_schema_v2.sql

-- Create import logs table for tracking CSV import operations
CREATE TABLE IF NOT EXISTS import_logs (
    id BIGSERIAL PRIMARY KEY,
    file_name VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('SUCCESS', 'FAILED', 'PARTIAL', 'PROCESSING')),
    total_rows INTEGER NOT NULL DEFAULT 0,
    success_rows INTEGER NOT NULL DEFAULT 0,
    error_rows INTEGER NOT NULL DEFAULT 0,
    error_details JSONB, -- Store row-level errors as JSON array
    file_size_mb NUMERIC(10,3),
    processing_time_ms INTEGER,
    imported_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_import_logs_status ON import_logs(status);
CREATE INDEX IF NOT EXISTS idx_import_logs_imported_at ON import_logs(imported_at DESC);

-- Create function to update import log status
CREATE OR REPLACE FUNCTION update_import_status(
    log_id BIGINT,
    new_status VARCHAR(20),
    success_count INTEGER DEFAULT NULL,
    error_count INTEGER DEFAULT NULL,
    errors JSONB DEFAULT NULL,
    process_time INTEGER DEFAULT NULL
) RETURNS VOID AS $$
BEGIN
    UPDATE import_logs
    SET
        status = new_status,
        success_rows = COALESCE(success_count, success_rows),
        error_rows = COALESCE(error_count, error_rows),
        error_details = COALESCE(errors, error_details),
        processing_time_ms = COALESCE(process_time, processing_time_ms)
    WHERE id = log_id;
END;
$$ LANGUAGE plpgsql;

-- Add sample data for testing (optional)
-- INSERT INTO prices (title, price, source, sku) VALUES
-- ('Офисная мебель', 150000, 'csv', 'ITEM-001'),
-- ('Компьютерное оборудование', 250000, 'csv', 'ITEM-002'),
-- ('Канцелярские товары', 15000, 'csv', 'ITEM-003');
COMMENT ON TABLE import_logs IS 'Log of CSV import operations with status and error tracking';
