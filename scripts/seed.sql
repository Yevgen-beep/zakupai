-- Seed data for ZakupAI database

-- Suppliers
INSERT INTO suppliers (name, bin, oked, region, created_at)
VALUES
  ('ТОО "Техносервис"', '123456789012', 'IT-услуги', 'Алматы', now()),
  ('ИП Иванов С.А.', '987654321098', 'Торговля', 'Нур-Султан', now())
ON CONFLICT (bin) DO NOTHING;

-- Lots
INSERT INTO lots (title, price, deadline, customer_bin, plan_id, created_at)
VALUES
  ('Поставка картриджей HP LaserJet', 850000.00, '2025-09-15'::date, '990840001234', 'PLAN-2025-001', now()),
  ('Канцелярские товары для офиса', 320000.00, '2025-09-20'::date, '990840001234', null, now())
ON CONFLICT DO NOTHING;

-- Prices
INSERT INTO prices (source, sku, title, price, captured_at)
VALUES
  ('kaspi.kz', 'HP-305A-BK', 'Картридж HP 305A черный', 18500.00, now()),
  ('kaspi.kz', 'HP-305A-C', 'Картридж HP 305A голубой', 19200.00, now()),
  ('dns.kz', 'HP-305A-M', 'Картридж HP 305A пурпурный', 19800.00, now())
ON CONFLICT DO NOTHING;

-- Lot prices (linking lots with prices)
INSERT INTO lot_prices (lot_id, price_id, qty)
VALUES
  ((SELECT id FROM lots WHERE title LIKE 'Поставка картриджей%' LIMIT 1),
   (SELECT id FROM prices WHERE sku = 'HP-305A-BK' LIMIT 1),
   20),
  ((SELECT id FROM lots WHERE title LIKE 'Поставка картриджей%' LIMIT 1),
   (SELECT id FROM prices WHERE sku = 'HP-305A-C' LIMIT 1),
   15)
ON CONFLICT DO NOTHING;
