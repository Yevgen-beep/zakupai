-- Advanced Search Performance Indexes for ZakupAI
-- Indexes for Russian full-text search and filtering optimization

-- 1. GIN index for Russian full-text search on lots.nameRu
-- This enables fast full-text search with Russian language support
CREATE INDEX IF NOT EXISTS idx_lots_nameRu_gin
ON lots USING GIN (to_tsvector('russian', nameRu));

-- 2. GIN index for Russian full-text search on lots.descriptionRu
-- For comprehensive text search across descriptions
CREATE INDEX IF NOT EXISTS idx_lots_descriptionRu_gin
ON lots USING GIN (to_tsvector('russian', descriptionRu));

-- 3. GIN index for Russian full-text search on trdbuy.nameRu
-- For searching tender/purchase names
CREATE INDEX IF NOT EXISTS idx_trdbuy_nameRu_gin
ON trdbuy USING GIN (to_tsvector('russian', nameRu));

-- 4. Index for amount filtering on lots
-- Optimizes min_amount and max_amount filters
CREATE INDEX IF NOT EXISTS idx_lots_amount
ON lots(amount) WHERE amount IS NOT NULL;

-- 5. Index for status filtering on trdbuy
-- Optimizes status filters (refBuyStatusId)
CREATE INDEX IF NOT EXISTS idx_trdbuy_status
ON trdbuy(refBuyStatusId) WHERE refBuyStatusId IS NOT NULL;

-- 6. Composite index for lots joined with trdbuy
-- Optimizes JOIN operations between lots and trdbuy tables
CREATE INDEX IF NOT EXISTS idx_lots_trdbuy_composite
ON lots(trdBuyId, amount DESC, lastUpdateDate DESC);

-- 7. Index for date range filtering
-- Optimizes publishDate and endDate filters
CREATE INDEX IF NOT EXISTS idx_trdbuy_dates
ON trdbuy(publishDate, endDate) WHERE publishDate IS NOT NULL;

-- 8. Index for customer filtering
-- Optimizes customer-based searches
CREATE INDEX IF NOT EXISTS idx_trdbuy_customer
ON trdbuy(customerBin, publishDate DESC) WHERE customerBin IS NOT NULL;

-- 9. Covering index for frequent search combinations
-- Reduces index lookups for common search patterns
CREATE INDEX IF NOT EXISTS idx_lots_search_covering
ON lots(trdBuyId, amount, lastUpdateDate DESC)
INCLUDE (nameRu, descriptionRu);

-- 10. Index for autocomplete functionality
-- Optimizes prefix matching for autocomplete suggestions
CREATE INDEX IF NOT EXISTS idx_lots_nameRu_prefix
ON lots(nameRu text_pattern_ops) WHERE nameRu IS NOT NULL;

-- Comments for documentation
COMMENT ON INDEX idx_lots_nameRu_gin IS 'GIN index for Russian full-text search on lot names';
COMMENT ON INDEX idx_lots_descriptionRu_gin IS 'GIN index for Russian full-text search on lot descriptions';
COMMENT ON INDEX idx_trdbuy_nameRu_gin IS 'GIN index for Russian full-text search on tender names';
COMMENT ON INDEX idx_lots_amount IS 'B-tree index for amount range filtering';
COMMENT ON INDEX idx_trdbuy_status IS 'B-tree index for status filtering';
COMMENT ON INDEX idx_lots_trdbuy_composite IS 'Composite index for optimized lot-tender joins';
COMMENT ON INDEX idx_trdbuy_dates IS 'Composite index for date range filtering';
COMMENT ON INDEX idx_trdbuy_customer IS 'Index for customer-based searches with date ordering';
COMMENT ON INDEX idx_lots_search_covering IS 'Covering index for frequent search patterns';
COMMENT ON INDEX idx_lots_nameRu_prefix IS 'Index for autocomplete prefix matching';

-- Performance analysis queries for monitoring
-- These queries can be used to monitor index usage and performance

/*
-- Query to check index usage statistics:
SELECT
    schemaname,
    tablename,
    indexname,
    idx_tup_read,
    idx_tup_fetch,
    idx_scan
FROM pg_stat_user_indexes
WHERE indexname LIKE 'idx_lots_%' OR indexname LIKE 'idx_trdbuy_%'
ORDER BY idx_scan DESC;

-- Query to analyze table sizes after index creation:
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) as index_size
FROM pg_tables
WHERE tablename IN ('lots', 'trdbuy', 'subjects', 'contracts')
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Query to check full-text search configuration:
SELECT cfgname, cfgparser, cfgdict
FROM pg_ts_config
WHERE cfgname = 'russian';
*/
