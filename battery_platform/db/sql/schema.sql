
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Her suruş/test oturumunu temsil eden tablo
CREATE TABLE IF NOT EXISTS session (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pack_id TEXT NOT NULL,
    driving_style TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS pack_reading (
    time TIMESTAMPTZ NOT NULL,
    session_id UUID NOT NULL REFERENCES session(session_id),
    pack_id TEXT NOT NULL,
    pack_voltage DOUBLE PRECISION,
    pack_soc DOUBLE PRECISION,
    max_temperature_c DOUBLE PRECISION,
    cell_voltage_delta DOUBLE PRECISION,
    current_a DOUBLE PRECISION,
    soh_percent DOUBLE PRECISION,
    thermal_state TEXT
);
SELECT create_hypertable('pack_reading', 'time', if_not_exists => TRUE);

-- Hucre seviyesinde detayli veri (hypertable)
CREATE TABLE IF NOT EXISTS cell_reading (
    time TIMESTAMPTZ NOT NULL,
    session_id UUID NOT NULL REFERENCES session(session_id),
    cell_id TEXT NOT NULL,
    soc DOUBLE PRECISION,
    voltage DOUBLE PRECISION,
    temperature_c DOUBLE PRECISION,
    balancing_active BOOLEAN
);

SELECT create_hypertable('cell_reading', 'time', if_not_exists => TRUE);

-- Sorgu performansi icin indexler
CREATE INDEX IF NOT EXISTS idx_pack_reading_session_time
    ON pack_reading (session_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_cell_reading_session_cell_time
    ON cell_reading (session_id, cell_id, time DESC);