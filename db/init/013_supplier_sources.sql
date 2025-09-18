-- Week 4.2: Supplier Sources Configuration
-- Modular supplier sources with rate limiting and fallback support

-- Create supplier_sources table for modular source management
CREATE TABLE IF NOT EXISTS supplier_sources (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    url_template VARCHAR(255) NOT NULL,
    parser_type VARCHAR(20) NOT NULL CHECK (parser_type IN ('api', 'web_search', 'mock')),
    auth_type VARCHAR(10) NOT NULL CHECK (auth_type IN ('NONE', 'API_KEY', 'MCP')),
    credentials_ref VARCHAR(100),
    rate_limit INTEGER DEFAULT 100,
    fallback_type VARCHAR(20) DEFAULT 'web_search',
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_supplier_sources_active_name ON supplier_sources(active, name);
CREATE INDEX IF NOT EXISTS idx_supplier_sources_parser_type ON supplier_sources(parser_type);

-- Insert default supplier sources
INSERT INTO supplier_sources (name, url_template, parser_type, auth_type, credentials_ref, rate_limit) VALUES
('Satu.kz', 'https://satu.kz/search?q={query}', 'mock', 'NONE', NULL, 1000),
('1688', 'https://rapidapi.com/open-trade-commerce-default/api/otapi-1688', 'api', 'API_KEY', 'RAPIDAPI_KEY', 100),
('Alibaba', 'https://rapidapi.com/open-trade-commerce-default/api/otapi-alibaba', 'api', 'API_KEY', 'RAPIDAPI_KEY', 100)
ON CONFLICT (name) DO NOTHING;

-- Create complaints table for storing generated complaints
CREATE TABLE IF NOT EXISTS complaints (
    id BIGSERIAL PRIMARY KEY,
    lot_id INTEGER NOT NULL,
    reason VARCHAR(200) NOT NULL,
    complaint_date DATE NOT NULL,
    content TEXT NOT NULL,
    source VARCHAR(20) NOT NULL CHECK (source IN ('flowise', 'fallback')),
    format VARCHAR(10) NOT NULL CHECK (format IN ('text', 'pdf', 'word')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    FOREIGN KEY (lot_id) REFERENCES lots(id) ON DELETE CASCADE
);

-- Performance indexes for complaints
CREATE INDEX IF NOT EXISTS idx_complaints_lot_id ON complaints(lot_id);
CREATE INDEX IF NOT EXISTS idx_complaints_date ON complaints(complaint_date DESC);
CREATE INDEX IF NOT EXISTS idx_complaints_source ON complaints(source);

-- Create suppliers cache table for search results
CREATE TABLE IF NOT EXISTS suppliers_cache (
    id BIGSERIAL PRIMARY KEY,
    query_hash VARCHAR(32) NOT NULL,
    source_name VARCHAR(50) NOT NULL,
    name VARCHAR(200) NOT NULL,
    region VARCHAR(10) NOT NULL,
    budget DECIMAL(20,2) NOT NULL,
    rating DECIMAL(3,2) NOT NULL DEFAULT 0.0,
    link TEXT,
    cached_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE DEFAULT (NOW() + INTERVAL '48 hours')
);

-- Performance indexes for suppliers cache
CREATE INDEX IF NOT EXISTS idx_suppliers_cache_query_source ON suppliers_cache(query_hash, source_name);
CREATE INDEX IF NOT EXISTS idx_suppliers_cache_expires ON suppliers_cache(expires_at);
CREATE INDEX IF NOT EXISTS idx_suppliers_cache_region ON suppliers_cache(region);

-- Cleanup function for expired cache entries
CREATE OR REPLACE FUNCTION cleanup_suppliers_cache()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM suppliers_cache WHERE expires_at < NOW();
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Add a trigger to update updated_at timestamp on supplier_sources
CREATE OR REPLACE FUNCTION update_supplier_sources_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_supplier_sources_updated_at
    BEFORE UPDATE ON supplier_sources
    FOR EACH ROW
    EXECUTE FUNCTION update_supplier_sources_updated_at();

-- Performance statistics view
CREATE OR REPLACE VIEW supplier_performance_stats AS
SELECT
    ss.name,
    ss.active,
    ss.rate_limit,
    COUNT(sc.id) as cached_results,
    AVG(sc.rating) as avg_rating,
    COUNT(DISTINCT sc.region) as regions_covered,
    MAX(sc.cached_at) as last_cached
FROM supplier_sources ss
LEFT JOIN suppliers_cache sc ON ss.name = sc.source_name
GROUP BY ss.id, ss.name, ss.active, ss.rate_limit
ORDER BY ss.name;
