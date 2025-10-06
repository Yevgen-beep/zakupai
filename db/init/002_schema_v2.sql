-- V2: расширение лотов + базовые сущности

-- 1) lots: новые поля
ALTER TABLE IF EXISTS lots
  ADD COLUMN IF NOT EXISTS risk_score NUMERIC(5,2),
  ADD COLUMN IF NOT EXISTS deadline DATE,
  ADD COLUMN IF NOT EXISTS customer_bin TEXT,
  ADD COLUMN IF NOT EXISTS plan_id TEXT,
  ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT now(),
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_lots_deadline      ON lots(deadline);
CREATE INDEX IF NOT EXISTS idx_lots_customer_bin  ON lots(customer_bin);

-- 2) suppliers (поставщики)
CREATE TABLE IF NOT EXISTS suppliers (
  bin         TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  oked        TEXT,
  region      TEXT,
  created_at  TIMESTAMP DEFAULT now()
);

-- 3) prices (источники рыночных цен)
CREATE TABLE IF NOT EXISTS prices (
  id          BIGSERIAL PRIMARY KEY,
  source      TEXT NOT NULL,          -- e.g. 'csv', '1688', 'alibaba', 'manual'
  sku         TEXT NOT NULL,
  title       TEXT,
  price       NUMERIC(18,2) NOT NULL,
  currency    TEXT DEFAULT 'KZT',
  captured_at TIMESTAMP DEFAULT now()
);
ALTER TABLE IF EXISTS prices
  ADD COLUMN IF NOT EXISTS captured_at TIMESTAMP DEFAULT now();
CREATE INDEX IF NOT EXISTS idx_prices_sku ON prices(sku);

-- 4) lot_prices (связка лота с рыночными ценами/сметой)
CREATE TABLE IF NOT EXISTS lot_prices (
  id          BIGSERIAL PRIMARY KEY,
  lot_id      INT NOT NULL REFERENCES lots(id) ON DELETE CASCADE,
  price_id    BIGINT REFERENCES prices(id) ON DELETE SET NULL,
  qty         NUMERIC(18,3) DEFAULT 1,
  note        TEXT
);
CREATE INDEX IF NOT EXISTS idx_lot_prices_lot_id ON lot_prices(lot_id);

-- 5) risk_evaluations (храним скора и флаги)
CREATE TABLE IF NOT EXISTS risk_evaluations (
  id            BIGSERIAL PRIMARY KEY,
  lot_id        INT NOT NULL REFERENCES lots(id) ON DELETE CASCADE,
  model_version TEXT,                 -- версия правил/модели
  score         NUMERIC(5,2),         -- итоговый риск-скор
  flags         JSONB,                -- подробные флаги/объяснение
  created_at    TIMESTAMP DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_risk_eval_lot_id ON risk_evaluations(lot_id);

-- 6) finance_calcs (результаты НДС/маржи/пени)
CREATE TABLE IF NOT EXISTS finance_calcs (
  id            BIGSERIAL PRIMARY KEY,
  lot_id        INT REFERENCES lots(id) ON DELETE CASCADE,
  input         JSONB,                -- входные параметры
  results       JSONB,                -- готовые расчёты
  created_at    TIMESTAMP DEFAULT now()
);

-- helper триггер обновления updated_at
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS lots_set_updated_at ON lots;
CREATE TRIGGER lots_set_updated_at
BEFORE UPDATE ON lots
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
