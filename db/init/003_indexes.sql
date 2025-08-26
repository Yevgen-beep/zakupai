-- Database performance indexes for ZakupAI

CREATE INDEX IF NOT EXISTS idx_lots_customer_deadline ON lots(customer_bin, deadline);
CREATE INDEX IF NOT EXISTS idx_prices_sku ON prices(sku);
CREATE INDEX IF NOT EXISTS idx_prices_captured_at ON prices(captured_at);
CREATE INDEX IF NOT EXISTS idx_riskeval_lot_created ON risk_evaluations(lot_id, created_at DESC);
