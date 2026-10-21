-- Faz 5: olay kaydı tablosu (termal geçişler, arıza enjeksiyonları, profil değişiklikleri)
CREATE TABLE IF NOT EXISTS event (
    time        TIMESTAMPTZ NOT NULL DEFAULT now(),
    session_id  UUID REFERENCES session(session_id),
    pack_id     TEXT NOT NULL,
    event_type  TEXT NOT NULL,
    severity    TEXT NOT NULL DEFAULT 'info',
    message     TEXT NOT NULL,
    details     JSONB DEFAULT '{}'::jsonb
);

SELECT create_hypertable('event', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_event_pack_time
    ON event (pack_id, time DESC);
