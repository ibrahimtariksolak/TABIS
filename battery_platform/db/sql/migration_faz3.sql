-- Faz 3: SoH ve termal durum kolonlarini pack_reading tablosuna ekler
ALTER TABLE pack_reading ADD COLUMN IF NOT EXISTS soh_percent DOUBLE PRECISION;
ALTER TABLE pack_reading ADD COLUMN IF NOT EXISTS thermal_state TEXT;