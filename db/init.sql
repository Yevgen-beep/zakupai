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

-- 6. Создание индексов
CREATE INDEX idx_subjects_bin ON subjects(bin) WHERE bin IS NOT NULL;
CREATE INDEX idx_trdbuy_customer_bin ON trdbuy(customerBin) WHERE customerBin IS NOT NULL;
CREATE INDEX idx_trdbuy_publish_date ON trdbuy(publishDate);
CREATE INDEX idx_lots_trdbuy_id ON lots(trdBuyId);
CREATE INDEX idx_contracts_trdbuy_id ON contracts(trdBuyId) WHERE trdBuyId IS NOT NULL;
CREATE INDEX idx_contracts_supplier_bin ON contracts(supplierBin) WHERE supplierBin IS NOT NULL;
CREATE INDEX idx_contracts_sign_date ON contracts(signDate);
CREATE INDEX idx_rnu_bin ON rnu(bin);

-- 7. Финальное предоставление прав на созданные объекты
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO zakupai;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO zakupai;
