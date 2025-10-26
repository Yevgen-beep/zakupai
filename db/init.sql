-- 1. Создаём пользователя zakupai с паролем
DO $$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'zakupai') THEN
      CREATE ROLE zakupai WITH LOGIN PASSWORD 'zakupai';
   END IF;
END
$$;

-- 2. Создаём базу zakupai и назначаем владельца zakupai
SELECT 'CREATE DATABASE zakupai OWNER zakupai'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'zakupai')\gexec

-- 3. Переключаемся в базу zakupai
\c zakupai;

-- 4. Предоставляем права пользователю zakupai
GRANT ALL PRIVILEGES ON DATABASE zakupai TO zakupai;
GRANT ALL PRIVILEGES ON SCHEMA public TO zakupai;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO zakupai;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO zakupai;

-- 5. Создаём таблицы

-- Основная таблица участников системы
CREATE TABLE subjects (
    id BIGINT PRIMARY KEY,
    bin VARCHAR(12) UNIQUE,
    iin VARCHAR(12),
    nameRu TEXT,
    okedCode VARCHAR(10),
    regionCode VARCHAR(10),
    markSmallEmployer BOOLEAN DEFAULT FALSE,
    markPatronymicSupplier BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
ALTER TABLE subjects OWNER TO zakupai;

-- Торговые процедуры/объявления о закупках
CREATE TABLE trdbuy (
    id BIGINT PRIMARY KEY,
    publishDate TIMESTAMP,
    endDate TIMESTAMP,
    customerBin VARCHAR(12),
    customerNameRu TEXT,
    refBuyStatusId INT,
    nameRu TEXT,
    totalSum NUMERIC(20,2),
    numberAnno TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customerBin) REFERENCES subjects(bin) ON DELETE SET NULL
);
ALTER TABLE trdbuy OWNER TO zakupai;

-- Лоты
CREATE TABLE lots (
    id BIGINT PRIMARY KEY,
    trdBuyId BIGINT NOT NULL,
    nameRu TEXT,
    amount NUMERIC(20,2),
    descriptionRu TEXT,
    lastUpdateDate TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (trdBuyId) REFERENCES trdbuy(id) ON DELETE CASCADE
);
ALTER TABLE lots OWNER TO zakupai;

-- Контракты
CREATE TABLE contracts (
    id BIGINT PRIMARY KEY,
    trdBuyId BIGINT,
    contractSum NUMERIC(20,2),
    signDate TIMESTAMP,
    supplierBin VARCHAR(12),
    supplierNameRu TEXT,
    executionStatus TEXT,
    contractNumber TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (trdBuyId) REFERENCES trdbuy(id) ON DELETE CASCADE,
    FOREIGN KEY (supplierBin) REFERENCES subjects(bin) ON DELETE SET NULL
);
ALTER TABLE contracts OWNER TO zakupai;

-- Реестр недобросовестных участников
CREATE TABLE rnu (
    id BIGINT PRIMARY KEY,
    bin VARCHAR(12) NOT NULL,
    nameRu TEXT,
    decisionDate DATE,
    decisionReason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (bin) REFERENCES subjects(bin) ON DELETE CASCADE
);
ALTER TABLE rnu OWNER TO zakupai;

-- 6. Создание индексов
CREATE INDEX idx_subjects_bin ON subjects(bin) WHERE bin IS NOT NULL;
CREATE INDEX idx_trdbuy_customer_bin ON trdbuy(customerBin) WHERE customerBin IS NOT NULL;
CREATE INDEX idx_trdbuy_publish_date ON trdbuy(publishDate);
CREATE INDEX idx_lots_trdbuy_id ON lots(trdBuyId);
CREATE INDEX idx_contracts_trdbuy_id ON contracts(trdBuyId) WHERE trdBuyId IS NOT NULL;
CREATE INDEX idx_contracts_supplier_bin ON contracts(supplierBin) WHERE supplierBin IS NOT NULL;
CREATE INDEX idx_contracts_sign_date ON contracts(signDate);
CREATE INDEX idx_rnu_bin ON rnu(bin);

-- Дополнительные доменные сущности для аналитики и импортов (Week 4)
ALTER TABLE lots
    ADD COLUMN IF NOT EXISTS title TEXT,
    ADD COLUMN IF NOT EXISTS price NUMERIC(20,2),
    ADD COLUMN IF NOT EXISTS deadline DATE,
    ADD COLUMN IF NOT EXISTS customer_bin TEXT,
    ADD COLUMN IF NOT EXISTS plan_id TEXT;

CREATE TABLE IF NOT EXISTS suppliers (
    bin TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    oked TEXT,
    region TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
ALTER TABLE suppliers OWNER TO zakupai;

CREATE TABLE IF NOT EXISTS prices (
    id BIGSERIAL PRIMARY KEY,
    source TEXT,
    sku TEXT,
    title TEXT,
    product_name TEXT,
    amount NUMERIC(20,2) CHECK (amount IS NULL OR amount >= 0),
    price NUMERIC(20,2) CHECK (price IS NULL OR price >= 0),
    supplier_bin VARCHAR(12) REFERENCES suppliers(bin) ON DELETE SET NULL,
    currency TEXT DEFAULT 'KZT',
    imported_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
ALTER TABLE prices OWNER TO zakupai;
CREATE INDEX IF NOT EXISTS idx_prices_sku ON prices(sku);
CREATE INDEX IF NOT EXISTS idx_prices_supplier_bin ON prices(supplier_bin);
CREATE INDEX IF NOT EXISTS idx_prices_imported_at ON prices(imported_at DESC);

CREATE TABLE IF NOT EXISTS lot_prices (
    id BIGSERIAL PRIMARY KEY,
    lot_id BIGINT NOT NULL REFERENCES lots(id) ON DELETE CASCADE,
    price_id BIGINT REFERENCES prices(id) ON DELETE CASCADE,
    qty NUMERIC(18,3) DEFAULT 1,
    note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
ALTER TABLE lot_prices OWNER TO zakupai;
CREATE INDEX IF NOT EXISTS idx_lot_prices_lot_id ON lot_prices(lot_id);

CREATE TABLE IF NOT EXISTS risk_evaluations (
    id BIGSERIAL PRIMARY KEY,
    lot_id BIGINT NOT NULL REFERENCES lots(id) ON DELETE CASCADE,
    model_version TEXT,
    score NUMERIC(5,2),
    flags JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
ALTER TABLE risk_evaluations OWNER TO zakupai;
CREATE INDEX IF NOT EXISTS idx_risk_eval_lot_id ON risk_evaluations(lot_id);

CREATE TABLE IF NOT EXISTS finance_calcs (
    id BIGSERIAL PRIMARY KEY,
    lot_id BIGINT REFERENCES lots(id) ON DELETE CASCADE,
    input JSONB,
    results JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
ALTER TABLE finance_calcs OWNER TO zakupai;

CREATE TABLE IF NOT EXISTS import_logs (
    id BIGSERIAL PRIMARY KEY,
    file_name VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('SUCCESS', 'FAILED', 'PARTIAL', 'PROCESSING')),
    total_rows INTEGER NOT NULL DEFAULT 0,
    success_rows INTEGER NOT NULL DEFAULT 0,
    error_rows INTEGER NOT NULL DEFAULT 0,
    error_details JSONB,
    file_size_mb NUMERIC(10,3),
    processing_time_ms INTEGER,
    imported_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
ALTER TABLE import_logs OWNER TO zakupai;
CREATE INDEX IF NOT EXISTS idx_import_logs_status ON import_logs(status);
CREATE INDEX IF NOT EXISTS idx_import_logs_imported_at ON import_logs(imported_at DESC);

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

-- 7. Финальное предоставление прав на созданные объекты
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO zakupai;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO zakupai;
