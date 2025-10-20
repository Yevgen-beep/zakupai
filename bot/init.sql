-- ZakupAI Telegram Bot Database Schema
-- Создание таблиц для хранения данных Telegram бота

-- Таблица для хранения API ключей пользователей Telegram
CREATE TABLE IF NOT EXISTS tg_keys (
    user_id BIGINT PRIMARY KEY,
    api_key TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,

    CONSTRAINT tg_keys_api_key_not_empty CHECK (LENGTH(api_key) >= 10)
);

-- Индексы для оптимизации запросов
CREATE INDEX IF NOT EXISTS idx_tg_keys_user_id ON tg_keys(user_id);
CREATE INDEX IF NOT EXISTS idx_tg_keys_created_at ON tg_keys(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tg_keys_is_active ON tg_keys(is_active) WHERE is_active = TRUE;

-- Таблица для логирования активности пользователей (опционально)
CREATE TABLE IF NOT EXISTS tg_user_activity (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    command TEXT NOT NULL,
    lot_id TEXT,
    request_data JSONB,
    response_status TEXT,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES tg_keys(user_id) ON DELETE CASCADE
);

-- Индексы для таблицы активности
CREATE INDEX IF NOT EXISTS idx_tg_activity_user_id ON tg_user_activity(user_id);
CREATE INDEX IF NOT EXISTS idx_tg_activity_created_at ON tg_user_activity(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tg_activity_command ON tg_user_activity(command);

-- Таблица для кэширования результатов анализа лотов
CREATE TABLE IF NOT EXISTS tg_lot_cache (
    lot_id TEXT PRIMARY KEY,
    tldr_data JSONB,
    risk_data JSONB,
    finance_data JSONB,
    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP DEFAULT (CURRENT_TIMESTAMP + INTERVAL '1 hour'),

    CONSTRAINT tg_lot_cache_lot_id_not_empty CHECK (LENGTH(lot_id) > 0)
);

-- Индексы для кэша
CREATE INDEX IF NOT EXISTS idx_tg_cache_lot_id ON tg_lot_cache(lot_id);
CREATE INDEX IF NOT EXISTS idx_tg_cache_expires_at ON tg_lot_cache(expires_at);

-- Функция для автоматического обновления updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Триггер для автоматического обновления updated_at в tg_keys
DROP TRIGGER IF EXISTS update_tg_keys_updated_at ON tg_keys;
CREATE TRIGGER update_tg_keys_updated_at
    BEFORE UPDATE ON tg_keys
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Функция для очистки старого кэша
CREATE OR REPLACE FUNCTION cleanup_expired_cache()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM tg_lot_cache WHERE expires_at < CURRENT_TIMESTAMP;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Функция для получения статистики пользователей
CREATE OR REPLACE FUNCTION get_user_statistics()
RETURNS TABLE(
    total_users BIGINT,
    active_users BIGINT,
    inactive_users BIGINT,
    users_last_7_days BIGINT,
    users_last_30_days BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*) as total_users,
        COUNT(*) FILTER (WHERE is_active = TRUE) as active_users,
        COUNT(*) FILTER (WHERE is_active = FALSE) as inactive_users,
        COUNT(*) FILTER (WHERE updated_at >= CURRENT_TIMESTAMP - INTERVAL '7 days') as users_last_7_days,
        COUNT(*) FILTER (WHERE updated_at >= CURRENT_TIMESTAMP - INTERVAL '30 days') as users_last_30_days
    FROM tg_keys;
END;
$$ LANGUAGE plpgsql;

-- Создание тестовых данных (только для разработки)
DO $$
BEGIN
    -- Проверяем, что это не продакшн среда
    IF current_setting('application_name', true) LIKE '%test%'
       OR current_database() LIKE '%test%' THEN

        -- Вставляем тестового пользователя
        INSERT INTO tg_keys (user_id, api_key, is_active)
        VALUES (123456789, 'test-api-key-12345', true)
        ON CONFLICT (user_id) DO NOTHING;

        -- Вставляем тестовый кэш
        INSERT INTO tg_lot_cache (lot_id, tldr_data, risk_data, finance_data)
        VALUES (
            'test-lot-123',
            '{"title": "Тестовый лот", "price": 1000000, "customer": "Тестовый заказчик"}',
            '{"score": 0.3, "level": "low", "explanation": "Низкий риск"}',
            '{"vat_amount": 120000, "total_with_vat": 1120000}'
        )
        ON CONFLICT (lot_id) DO NOTHING;

        RAISE NOTICE 'Test data inserted successfully';
    ELSE
        RAISE NOTICE 'Production environment detected, skipping test data';
    END IF;
END $$;

-- Вывод информации о созданных объектах
DO $$
DECLARE
    table_count INTEGER;
    index_count INTEGER;
    function_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO table_count
    FROM information_schema.tables
    WHERE table_schema = 'public'
    AND table_name IN ('tg_keys', 'tg_user_activity', 'tg_lot_cache');

    SELECT COUNT(*) INTO index_count
    FROM pg_indexes
    WHERE schemaname = 'public'
    AND indexname LIKE 'idx_tg_%';

    SELECT COUNT(*) INTO function_count
    FROM information_schema.routines
    WHERE routine_schema = 'public'
    AND routine_name IN ('update_updated_at_column', 'cleanup_expired_cache', 'get_user_statistics');

    RAISE NOTICE '✅ Database schema created successfully:';
    RAISE NOTICE '   - Tables: %', table_count;
    RAISE NOTICE '   - Indexes: %', index_count;
    RAISE NOTICE '   - Functions: %', function_count;
END $$;
