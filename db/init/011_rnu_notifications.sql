-- RNU Notification System Tables
-- Migration 011: RNU alerts and subscriptions

-- Table for storing RNU alert notifications
CREATE TABLE rnu_alerts (
    id BIGSERIAL PRIMARY KEY,
    supplier_bin VARCHAR(12) NOT NULL REFERENCES rnu_validation_cache(supplier_bin),
    status rnu_supplier_status NOT NULL,
    previous_status rnu_supplier_status,
    notified_at TIMESTAMP NOT NULL DEFAULT now(),
    user_id BIGINT,
    notification_type VARCHAR(50) DEFAULT 'status_change',
    created_at TIMESTAMP DEFAULT now()
);

-- Table for user subscriptions to BIN monitoring
CREATE TABLE rnu_subscriptions (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    supplier_bin VARCHAR(12) NOT NULL,
    subscribed_at TIMESTAMP NOT NULL DEFAULT now(),
    is_active BOOLEAN DEFAULT true,
    telegram_user_id BIGINT,
    email VARCHAR(255),
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now(),
    UNIQUE(user_id, supplier_bin)
);

-- Indexes for performance
CREATE INDEX idx_rnu_alerts_supplier_bin ON rnu_alerts (supplier_bin, notified_at DESC);
CREATE INDEX idx_rnu_alerts_user_id ON rnu_alerts (user_id, notified_at DESC);
CREATE INDEX idx_rnu_alerts_status ON rnu_alerts (status, notified_at DESC);
CREATE INDEX idx_rnu_subscriptions_user_id ON rnu_subscriptions (user_id, is_active);
CREATE INDEX idx_rnu_subscriptions_bin ON rnu_subscriptions (supplier_bin, is_active);
CREATE INDEX idx_rnu_subscriptions_telegram ON rnu_subscriptions (telegram_user_id, is_active);

-- Trigger function to enforce max 100 active subscriptions per user
CREATE OR REPLACE FUNCTION check_max_subscriptions()
RETURNS TRIGGER AS $$
DECLARE
    active_count INTEGER;
BEGIN
    SELECT COUNT(*)
      INTO active_count
      FROM rnu_subscriptions
     WHERE user_id = NEW.user_id
       AND is_active = true
       AND (TG_OP = 'INSERT' OR id <> NEW.id);

    IF active_count >= 100 THEN
        RAISE EXCEPTION 'User cannot have more than 100 active subscriptions';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger on insert and update
CREATE TRIGGER enforce_max_subscriptions
    BEFORE INSERT OR UPDATE ON rnu_subscriptions
    FOR EACH ROW
    WHEN (NEW.is_active = true)
    EXECUTE FUNCTION check_max_subscriptions();

-- Comments
COMMENT ON TABLE rnu_alerts IS 'RNU supplier status change notifications';
COMMENT ON TABLE rnu_subscriptions IS 'User subscriptions to RNU supplier monitoring (max 100 per user)';
COMMENT ON COLUMN rnu_alerts.notification_type IS 'Type of notification: status_change, new_blocked, etc.';
COMMENT ON COLUMN rnu_subscriptions.telegram_user_id IS 'Telegram user ID for notifications';
COMMENT ON COLUMN rnu_subscriptions.email IS 'Email for notifications (optional)';
