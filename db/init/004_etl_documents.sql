-- V4: ETL documents table for OCR processing results

-- etl_documents: stores OCR-processed document content
CREATE TABLE IF NOT EXISTS etl_documents (
  id SERIAL PRIMARY KEY,
  lot_id TEXT,
  file_name TEXT NOT NULL,
  file_type TEXT NOT NULL,
  content TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT now(),
  CONSTRAINT etl_documents_unique_lot_file UNIQUE(lot_id, file_name)
);

-- Indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_etl_documents_lot_id ON etl_documents(lot_id);
CREATE INDEX IF NOT EXISTS idx_etl_documents_file_name ON etl_documents(file_name);
CREATE INDEX IF NOT EXISTS idx_etl_documents_created_at ON etl_documents(created_at);

-- Full-text search index on content (Russian language support)
CREATE INDEX IF NOT EXISTS idx_etl_documents_content_fts
ON etl_documents USING gin(to_tsvector('russian', content));

COMMENT ON TABLE etl_documents IS 'OCR-processed document content from PDF files';
COMMENT ON COLUMN etl_documents.lot_id IS 'Optional lot identifier for document association';
COMMENT ON COLUMN etl_documents.file_name IS 'Original file name of processed document';
COMMENT ON COLUMN etl_documents.file_type IS 'File type (pdf, jpg, png, etc.)';
COMMENT ON COLUMN etl_documents.content IS 'Extracted text content from OCR processing';
