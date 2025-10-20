-- Migration for attachments table
-- Stores OCR'd text content from PDF/ZIP files linked to lots

CREATE TABLE IF NOT EXISTS attachments (
    id BIGSERIAL PRIMARY KEY,
    lot_id BIGINT NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_type VARCHAR(10) NOT NULL DEFAULT 'pdf',
    content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Ensure uniqueness of lot_id + file_name combination
    CONSTRAINT unique_lot_file UNIQUE (lot_id, file_name)
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_attachments_lot_id ON attachments (lot_id);
CREATE INDEX IF NOT EXISTS idx_attachments_created_at ON attachments (created_at DESC);

-- Full-text search index for Russian content
CREATE INDEX IF NOT EXISTS idx_attachments_content_fulltext
ON attachments USING gin(to_tsvector('russian', content));

-- Add foreign key constraint to lots table if it exists
-- Note: This will only work if lots table exists
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'lots') THEN
        ALTER TABLE attachments
        ADD CONSTRAINT fk_attachments_lot_id
        FOREIGN KEY (lot_id) REFERENCES lots(id)
        ON DELETE CASCADE;
    END IF;
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- Update trigger for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_attachments_updated_at
    BEFORE UPDATE ON attachments
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Test query for verification
-- SELECT lot_id, file_name, LEFT(content, 200) as content_preview, created_at
-- FROM attachments
-- ORDER BY created_at DESC
-- LIMIT 5;
