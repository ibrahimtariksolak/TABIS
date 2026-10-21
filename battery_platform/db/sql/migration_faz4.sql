-- Faz 4: sürüş karakteri analizi için akım (current_a) kolonu ekler
ALTER TABLE pack_reading ADD COLUMN IF NOT EXISTS current_a DOUBLE PRECISION;